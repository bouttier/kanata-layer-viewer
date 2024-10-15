import asyncio
import json
from pathlib import Path


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
