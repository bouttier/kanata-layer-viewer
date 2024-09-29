from codecs import strict_errors
import json
import pkgutil
from xml.etree import ElementTree as ET
from pyparsing import PositionToken
from selenium import webdriver
import tempfile
from xkbcommon import xkb

from .parser import KanataConfigParser
from .constants import (
    CODE_ALIASES,
    ACTION_LABELS,
    LAYER_LABELS,
    KEY_SCANCODES,
    KEY_SYM_LABELS,
    KEY_STRING_LABELS,
)


def send(driver, cmd, params={}):
    resource = "/session/%s/chromium/send_command_and_get_result" % driver.session_id
    url = driver.command_executor._url + resource
    body = json.dumps({"cmd": cmd, "params": params})
    response = driver.command_executor._request("POST", url, body)
    return response.get("value")


class KanataLayerRenderer:
    def __init__(self, config_file, cache_dir, layout, variant):
        self.ctx = xkb.Context()
        self.keymap = self.ctx.keymap_new_from_names(layout=layout, variant=variant)
        cache_dir.mkdir(parents=True, exist_ok=True)
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
            key_scancode = KEY_SCANCODES[key_code]
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
        if key_sym in KEY_SYM_LABELS:
            return KEY_SYM_LABELS[key_sym]
        else:
            key_string = xkb.keysym_to_string(key_sym)
            if key_string is None:
                print(
                    f"Warning: no character for key sym '{key_sym}' "
                    f"(code '{key_code}', scancode '{key_scancode}', level {level})",
                )
                return
            elif key_string in KEY_STRING_LABELS:
                return KEY_STRING_LABELS[key_string]
            else:
                return key_string

    def action_to_label(self, action):
        match action:
            case str(action) if action in ACTION_LABELS:
                return ACTION_LABELS[action]
            case str(action) if action.startswith("🔣"):
                return action.removeprefix("🔣")
            case ["layer-while-held" | "layer-switch", name]:
                return LAYER_LABELS.get(name, f"⌨{name}")
            case ["mwheel-left", _, _]:
                return "🖰 ←"
            case ["mwheel-up", _, _]:
                return "🖰 ↑"
            case ["mwheel-down", _, _]:
                return "🖰 ↓"
            case ["mwheel-right", _, _]:
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

            key_loc = CODE_ALIASES.get(src, src)
            key = svg.find(f'.//g[@id="{key_loc}"]', ns)
            if key is None:
                print(f"Warning: can not find key '{key_loc}'")
                continue

            def set_key_action(action, pos_level=1, xkb_level=0, prefix="", suffix=""):

                if pos_level > 4:
                    print(
                        f"Warning: can not render action '{action}' at level {pos_level} on key {key_loc}"
                    )
                    return

                def set_key_label(
                    label,
                    pos_level=pos_level,
                    xkb_level=xkb_level,
                    prefix=prefix,
                    suffix=suffix,
                ):

                    def set_key_text(text, level):
                        if text is None:
                            return
                        text = prefix + text + suffix

                        if key_loc in ["Backspace", "AltLeft", "AltRight"]:
                            if level != 1:
                                return
                            level = None

                        # this does not match multi-class elements: f'g/text[@class="level{lvl}"]'
                        # this is not supported by python: f'g/text[contains(@class,"level{lvl}")]'
                        for n in key.findall("g/text", ns):
                            if level is not None:
                                classes = n.attrib["class"].split(" ")
                                if f"level{level}" not in classes:
                                    continue
                            n.text = text
                            break
                        else:
                            for n in key.findall(".//text", ns):
                                if level is not None:
                                    classes = n.attrib["class"].split(" ")
                                    if f"level{level}" not in classes:
                                        continue
                                n.text = text
                                break
                            else:
                                print(
                                    f"Warning: unable to set text '{text}' for key '{key_loc}' at level {level}"
                                )

                    match label:
                        case "XX":
                            pass
                        case str(mod) if mod.startswith("M-"):
                            mod = mod.removeprefix("M-")
                            set_key_label(mod, prefix="⌘")
                        case str(ctrl) if ctrl.startswith("C-"):
                            ctrl = ctrl.removeprefix("C-")
                            set_key_label(ctrl, prefix="^")
                        case str(shift) if shift.startswith("S-"):
                            shift = shift.removeprefix("S-")
                            set_key_label(shift, xkb_level=xkb_level + 1)
                        case str(altgr) if altgr.startswith("AG-"):
                            altgr = altgr.removeprefix("AG-")
                            set_key_label(altgr, xkb_level=xkb_level + 2)
                        case str(action) if xkb_level is not None:
                            set_key_text(
                                self.key_code_to_label(action, level=xkb_level)
                                or action,
                                level=pos_level,
                            )
                            if xkb_level % 2 == 0 and pos_level % 2 == 1:
                                set_key_text(
                                    self.key_code_to_label(action, level=xkb_level + 1),
                                    level=pos_level + 1,
                                )
                        case str(action) if xkb_level is None:
                            set_key_text(action, level=pos_level)

                match action:
                    case action if (label := self.action_to_label(action)):
                        set_key_label(label, xkb_level=None)
                    case str(label):
                        set_key_label(label)
                    case [
                        "tap-hold-press" | "tap-hold-release",
                        str(),
                        str(),
                        tap_action,
                        hold_action,
                    ]:
                        set_key_action(tap_action, pos_level=pos_level)
                        set_key_action(hold_action, pos_level=pos_level + 2)
                    case [
                        "fork",
                        left_action,
                        right_action,
                        [*modifiers],
                    ] if modifiers and set(modifiers) <= {"lsft", "rsft"}:
                        assert pos_level % 2 == 1
                        set_key_action(left_action, pos_level=pos_level)
                        set_key_action(right_action, pos_level=pos_level + 1)
                    case [
                        "fork",
                        left_action,
                        right_action,
                        [*modifiers],
                    ] if modifiers and set(modifiers) <= {"lmet", "rmet"}:
                        set_key_action(left_action, pos_level=pos_level)
                        if pos_level % 2 == 1:
                            set_key_action(
                                right_action,
                                pos_level=pos_level + 1,
                                prefix=prefix + "[⌘] ",
                            )
                    case [str(action), *_]:
                        print(f"Warning: unknown action '{action}'")
                        set_key_label(action, suffix=suffix + "*", xkb_level=None)
                    case _:
                        raise Exception(f"Unexpected action: '{action}'")

            set_key_action(action)

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
