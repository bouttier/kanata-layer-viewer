import asyncio
import tomllib
from pathlib import Path
from argparse import SUPPRESS, ArgumentParser, FileType
from os import environ

from .renderer import KanataLayerRenderer
from .client import KanataClient
from .viewer import KanataLayerViewer


async def init(kanata_config, cache_dir, hidden_layers, host, port, layout, variant):
    renderer = KanataLayerRenderer(
        config_file=kanata_config,
        cache_dir=cache_dir,
        layout=layout,
        variant=variant,
    )
    viewer = KanataLayerViewer(renderer, hidden_layers=hidden_layers)
    client = KanataClient(renderer, viewer, params={"host": host, "port": port})

    kanata_task = asyncio.create_task(client.run())
    viewer_task = asyncio.create_task(viewer.run())

    await asyncio.gather(kanata_task, viewer_task)


def main():
    parser = ArgumentParser(add_help=False)
    parser.add_argument("--config", type=FileType("rb"), default=SUPPRESS)

    args, remaining_args = parser.parse_known_args()
    config = None
    if "config" in args:
        config = args.config
    else:
        config_home = None
        if "XDG_CONFIG_HOME" in environ:
            config_home = Path(environ["XDG_CONFIG_HOME"])
        elif "HOME" in environ:
            config_home = Path(environ["HOME"]) / ".config"
        if config_home is not None:
            config_path = config_home / "kanata-layer-viewer" / "config.toml"
            if config_path.exists():
                config = config_path.open("rb")

    parser.add_argument("-h", "--help", action="help")
    parser.add_argument(
        "--hide", dest="hidden_layers", action="append", default=["base"]
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default="5829")
    parser.add_argument("--kanata-config", default="/etc/kanata/kanata.kbd", type=Path)
    cache_home = None
    if "XDG_CACHE_HOME" in environ:
        cache_home = Path(environ["XDG_CACHE_HOME"])
    elif "HOME" in environ:
        cache_home = Path(environ["HOME"]) / ".cache"
    if cache_home:
        # parser.set_defaults(cache_dir=cache_home / "kanata-layers")
        parser.add_argument(
            "--cache-dir", type=Path, default=cache_home / "kanata-layers"
        )
    else:
        parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--layout")
    parser.add_argument("--variant")

    if config is not None:
        defaults = tomllib.load(config)
        parser.set_defaults(**defaults)

    args = parser.parse_args(remaining_args)
    asyncio.run(init(**vars(args)))


if __name__ == "__main__":
    main()
