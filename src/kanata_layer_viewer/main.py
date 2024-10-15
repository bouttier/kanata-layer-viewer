import asyncio
from pathlib import Path

from .renderer import KanataLayerRenderer
from .client import KanataClient
from .viewer import KanataLayerViewer


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
