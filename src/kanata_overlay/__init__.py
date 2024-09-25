import asyncio
import json
import subprocess
import pkgutil
from os import environ
from xml.etree import ElementTree as ET
from selenium import webdriver
import tempfile
from xkbcommon import xkb
import pyparsing as pp
from pathlib import Path
from i3ipc.aio import Connection
from i3ipc import Event


def send(driver, cmd, params={}):
    resource = "/session/%s/chromium/send_command_and_get_result" % driver.session_id
    url = driver.command_executor._url + resource
    body = json.dumps({"cmd": cmd, "params": params})
    response = driver.command_executor._request("POST", url, body)
    return response.get("value")


class KanataConfigParser:
    remove_comments = (";;" + pp.restOfLine).suppress()

    @classmethod
    def parse(cls, path: Path):
        srckeys = []
        aliases = {}
        layers = {}

        for section in cls._read(path):
            match section:
                case ["defalias", *args]:
                    aliases |= dict(zip(args[::2], args[1::2]))
                case ["deflayer", layer_name, *keys]:
                    layers[layer_name] = keys
                case ["defsrc", *keys]:
                    srckeys = keys
                case ["defvar" | "defcfg", *args]:
                    pass
                case _:
                    print("Warning: unknown section", section)

        return {"aliases": aliases, "srckeys": srckeys, "layers": layers}

    @classmethod
    def _read(cls, path: Path):
        source = path.open().read()
        source = cls.remove_comments.transform_string(source)
        section = pp.nested_expr(ignore_expr=None)
        config = pp.ZeroOrMore(section).parse_string(source)
        for section in config:
            match section:
                case ["include", other_path]:
                    other_path = path.resolve().parent / other_path
                    yield from cls._read(other_path)
                case _:
                    yield section


class KanataLayerRenderer:
    CODE_ALIASES = {
        **{f"{i}": f"Digit{i}" for i in range(10)},
        **{k: f"Key{k.upper()}" for k in "abcdefghijklmnopqrstuvwxyz"},
        "bspc": "Backspace",
        "spc": "Space",
        ";": "Semicolon",
        ",": "Comma",
        "<": "IntlBackslash",
        ".": "Period",
        "/": "Slash",
        "lalt": "AltLeft",
        "ralt": "AltRight",
    }
    ACTION_LABELS = {
        "XX": "",
        "lalt": "⌥",
        "ralt": "⌥",
        "lctl": "⌃",
        "rctl": "⌃",
        "lmet": "⌘",
        "rmet": "⌘",
        "lsft": "⇧",
        "tab": "↹",
        "S-tab": "⇤",
        "home": "⇱",
        "end": "⇲",
        "up": "↑",
        "down": "↓",
        "lft": "←",
        "rght": "→",
        "pgup": "⇞",
        "pgdn": "⇟",
        "bck": "⎗",
        "fwd": "⎘",
        # "mbck": "🖯",
        # "mmid": "🖯3",
        # "mlft": "🖯",
        # "mrgt": "🖯",
        # "mwu": "🖯",
        # "mwd": "🖯",
        # "mfwd": "🖯",
        "lrld": "↺",
        "ret": "⏎",
        "del": "⌦",
        "bspc": "⌫",
        "esc": "Esc",
        "C-a": "all",
        "C-z": "↶",
        "C-y": "↷",
        "C-x": "✀",
        # "C-c": "📄",
        "C-s": "💾",
        # "C-v": "📋",
        **{f"f{i}": f"F{i}" for i in range(1, 13)},
    }
    # should match https://github.com/jtroo/kanata/blob/main/parser/src/keys/linux.rs
    SCANCODES = {
        "q": 24,
        "w": 25,
        "e": 26,
        "r": 27,
        "t": 28,
        "y": 29,
        "u": 30,
        "i": 31,
        "o": 32,
        "p": 33,
        "a": 38,
        "s": 39,
        "d": 40,
        "f": 41,
        "g": 42,
        "h": 43,
        "j": 44,
        "k": 45,
        "l": 46,
        ";": 47,
        "'": 48,
        "<": 94,
        "z": 52,
        "x": 53,
        "c": 54,
        "v": 55,
        "b": 56,
        "n": 57,
        "m": 58,
        ",": 59,
        ".": 60,
        "/": 61,
        "1": 10,
        "2": 11,
        "3": 12,
        "4": 13,
        "5": 14,
        "6": 15,
        "7": 16,
        "8": 17,
        "9": 18,
        "0": 19,
        "del": 122,
        "spc": 65,
        "bspc": 119,
        "ret": 36,
        "lalt": 64,
        "ralt": 108,
        "tab": 23,
    }
    KEY_SYM_LABELS = {
        16777215: "",
        65107: "◌̃",
        65134: "◌̦",
        65116: "◌̨",
        65042: "★",
        65135: "¤",
        65115: "◌̧",
        65109: "◌̆",
        65114: "◌̌",
        65110: "◌̇",
        65112: "◌̊",
        65104: "◌̀",
        65105: "◌́",
        65113: "◌̋",
        65108: "◌̄",
        65513: "⌥",
        65511: "⌘",
    }
    KEY_STRING_LABELS = {
        " ": "espace",
        " ": "espace insécable fine",
    }

    def __init__(self, config_file, cache_dir=None):
        self.ctx = xkb.Context()
        self.keymap = self.ctx.keymap_new_from_names(layout="fr", variant="ergol")
        if cache_dir is None:
            if "XDG_CACHE_HOME" in environ:
                cache_home = environ["XDG_CACHE_HOME"]
            else:
                cache_home = Path(environ.get("HOME", "~")) / ".cache"
            cache_dir = cache_home / "kanata-layers"
        self.cache_dir = cache_dir
        self.load_config(config_file)

    def load_config(self, config_file):
        config = KanataConfigParser.parse(config_file)
        self.srckeys = config["srckeys"]
        self.kanata_aliases = config["aliases"]
        self.layers = config["layers"]
        self.render_layers()

    def render_layers(self):
        for layer in self.layers:
            self.render_layer(layer)

    def key_code_to_label(self, key_code, level=0):
        try:
            key_scancode = self.SCANCODES[key_code]
        except KeyError:
            print(f"Warning: unknown scancode for key '{key_code}'")
            return
        key_syms = self.keymap.key_get_syms_by_level(
            key_scancode, layout=0, level=level
        )
        if len(key_syms) != 1:
            print(
                "Warning: unexpected key syms "
                f"(code '{key_code}', scancode '{key_scancode}', level {level}):",
                key_syms,
            )
            return
        (key_sym,) = key_syms
        if key_sym in self.KEY_SYM_LABELS:
            return self.KEY_SYM_LABELS[key_sym]
        else:
            key_string = xkb.keysym_to_string(key_sym)
            if key_string is None:
                print(
                    f"Warning: no character for key sym '{key_sym}' "
                    f"(code '{key_code}', scancode '{key_scancode}', level {level})",
                )
                return
            elif key_string in self.KEY_STRING_LABELS:
                return self.KEY_STRING_LABELS[key_string]
            else:
                return key_string

    def action_to_label(self, action):
        match action:
            case str(action) if action in self.ACTION_LABELS:
                return self.ACTION_LABELS[action]
            case str(action) if action.startswith("C-"):
                return "^" + action.removeprefix("C-")
            case str(action) if action.startswith("🔣"):
                return action.removeprefix("🔣")
            case ["layer-while-held" | "layer-switch", name]:
                return f"⌨\n{name}"
            case ["mwheel-left", x, y]:
                return "🖰 ←"
            case ["mwheel-up", x, y]:
                return "🖰 ↑"
            case ["mwheel-down", x, y]:
                return "🖰 ↓"
            case ["mwheel-right", x, y]:
                return "🖰 →"

    def resolve_action_alias(self, action):
        match action:
            case str(alias) if alias.startswith("@"):
                try:
                    return self.resolve_action_alias(
                        self.kanata_aliases[alias.removeprefix("@")]
                    )
                except KeyError:
                    print(f"Warning: unknown alias '{alias}")
                    return alias
            case _:
                return action

    def render_layer(self, layer_name):
        print("Rendering layer:", layer_name)

        svg_ns = "http://www.w3.org/2000/svg"
        ET.register_namespace("", svg_ns)
        ns = {"": svg_ns}

        template = pkgutil.get_data("kalamine", "templates/x-keyboard.svg").decode(
            "utf-8"
        )
        svg = ET.ElementTree(ET.fromstring(template))

        geometries = {
            "alt": "alt intlYen",
            "ks": "alt intlYen ks",
            "jis": "iso intlYen intlRo jis",
            "abnt": "iso intlBackslash intlRo",
            "iso": "iso intlBackslash",
            "ansi": "",
            "ol60": "ergo ol60",
            "ol50": "ergo ol50",
            "ol40": "ergo ol40",
        }
        root = svg.getroot()
        root.attrib["class"] = geometries["iso"] + " altgr"

        for src, action in zip(self.srckeys, self.layers[layer_name]):
            if action == "_":
                action = src
            action = self.resolve_action_alias(action)

            key_loc = self.CODE_ALIASES.get(src, src)
            key = svg.find(f'.//g[@id="{key_loc}"]', ns)
            if key is None:
                print(f"Warning: can not find key '{key_loc}'")
                continue

            def set_key_label(label, level):
                if label is None:
                    return
                if key_loc in ["Backspace", "AltLeft", "AltRight"]:
                    if level != 1:
                        return
                    level = None
                # print("set", key_loc, label, level)
                # this does not match multi-class elements: f'g/text[@class="level{lvl}"]'
                # this is not supported by python: f'g/text[contains(@class,"level{lvl}")]'
                for n in key.findall("g/text", ns):
                    if level is not None:
                        classes = n.attrib["class"].split(" ")
                        if f"level{level}" not in classes:
                            continue
                    n.text = label
                    break
                else:
                    for n in key.findall(".//text", ns):
                        if level is not None:
                            classes = n.attrib["class"].split(" ")
                            if f"level{level}" not in classes:
                                continue
                        n.text = label
                        break
                    else:
                        print(
                            f"Warning: unable to set label '{label}' for key '{key_loc}' at level {level}"
                        )

            match action:
                case "XX":
                    pass
                case action if (label := self.action_to_label(action)):
                    set_key_label(label, level=1)
                case str(mod) if mod.startswith("M-"):
                    mod = mod.removeprefix("M-")
                    set_key_label(
                        "⌘" + (self.key_code_to_label(mod, level=0) or mod), level=1
                    )
                case str(shift) if shift.startswith("S-"):
                    shift = shift.removeprefix("S-")
                    set_key_label(
                        self.key_code_to_label(shift, level=1) or shift, level=1
                    )
                case str(altgr) if altgr.startswith("AG-"):
                    altgr = altgr.removeprefix("AG-")
                    set_key_label(
                        self.key_code_to_label(altgr, level=2) or altgr, level=1
                    )
                    set_key_label(self.key_code_to_label(altgr, level=3), level=2)
                case str(action):
                    set_key_label(
                        self.key_code_to_label(action, level=0) or action, level=1
                    )
                    set_key_label(self.key_code_to_label(action, level=1), level=2)
                case [
                    "tap-hold-press" | "tap-hold-release",
                    tap_timeout,
                    hold_timeout,
                    tap_action,
                    hold_action,
                ]:
                    for level, action in ((1, tap_action), (3, hold_action)):
                        label = self.action_to_label(action)
                        if label is not None:
                            set_key_label(label, level=level)
                        else:
                            set_key_label(
                                self.key_code_to_label(action, level=0), level=level
                            )
                            set_key_label(
                                self.key_code_to_label(action, level=1), level=level + 1
                            )
                case _:
                    print(f"Warning: unknown action '{action}'")

        svg = ET.tostring(svg.getroot())

        with tempfile.NamedTemporaryFile("wb", suffix=".svg") as svg_file:
            svg_file.write(svg)

            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            driver = webdriver.Chrome(options=options)
            driver.set_window_size(1920, 1080)
            driver.get(f"file://{svg_file.name}")
            send(
                driver,
                "Emulation.setDefaultBackgroundColorOverride",
                {"color": {"r": 0, "g": 0, "b": 0, "a": 0}},
            )
            driver.get_screenshot_as_file(self.get_rendered_layer_path(layer_name))
            driver.quit()

    def get_rendered_layer_path(self, name):
        return self.cache_dir / f"{name}.png"


class KanataClient:
    def __init__(self, renderer, viewer, params):
        self.renderer = renderer
        self.viewer = viewer
        self.params = params

    async def run(self):
        reader, writer = await asyncio.open_connection(**self.params)
        while True:
            line = await reader.readline()
            data = json.loads(line)
            match data:
                case {"LayerChange": {"new": name}}:
                    self.viewer.show(name)
                case {"ConfigFileReload": {"new": path}}:
                    self.renderer.load_config(Path(path))
                case _:
                    print("unknown message!", data)

    def layer_change(self, name):
        print("Active layer:", name)
        self.show_layer(name)


class KanataLayerViewer:
    def __init__(self, renderer):
        self.renderer = renderer
        self.process = None

    async def run(self):
        async def on_output(conn, event):
            tree = await conn.get_tree()
            focused = tree.find_by_id(event.container.id)
            focused_output = focused.workspace().ipc_data["output"]
            try:
                (layer,) = [c for c in tree if c.app_id == "kanata-layer-view"]
            except ValueError:
                return
            layer_output = layer.workspace().ipc_data["output"]
            if focused_output == layer_output:
                await layer.command("move container to output right")

        conn = await Connection(auto_reconnect=True).connect()
        conn.on(Event.WINDOW_FOCUS, on_output)

        await conn.main()

    def hide(self):
        if self.process is None:
            return
        self.process.terminate()
        self.process = None

    def show(self, name):
        self.hide()
        self.process = subprocess.Popen(
            [
                "swayimg",
                "--background=none",
                "--class=kanata-layer-view",
                "--scale=fit",
                self.renderer.get_rendered_layer_path(name),
            ],
        )
        return
        import pygame
        import os

        os.environ["SDL_VIDEO_WINDOW_POS"] = "20,20"
        pygame.init()
        pygame.display.set_caption("kanata-layer-viewer")
        img = pygame.image.load(png_file(name))
        w, h = img.get_width(), img.get_height()
        ratio = min(1080 / w, 720 / h)
        img = pygame.transform.smoothscale_by(img, ratio)
        surface = pygame.display.set_mode(
            (img.get_width(), img.get_height()), pygame.NOFRAME, display=1
        )
        while True:
            surface.fill((255, 255, 255))
            surface.blit(img, (0, 0))
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return
                pygame.display.update()
        return


async def init():
    renderer = KanataLayerRenderer(
        Path("/home/elie/data/git/arsenik/kanata/kanata.kbd"),
    )
    viewer = KanataLayerViewer(renderer)
    client = KanataClient(renderer, viewer, params={"host": "127.0.0.1", "port": 5829})

    kanata_task = asyncio.create_task(client.run())
    viewer_task = asyncio.create_task(viewer.run())

    await asyncio.gather(kanata_task, viewer_task)


def main():
    asyncio.run(init())


if __name__ == "__main__":
    main()
