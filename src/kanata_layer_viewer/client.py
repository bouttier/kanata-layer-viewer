import asyncio
import json
from pathlib import Path


class KanataClient:
    def __init__(self, renderer, viewer, params):
        self.renderer = renderer
        self.viewer = viewer
        self.params = params
        self.hidden_layer = ["base"]

    async def run(self):
        reader, writer = await asyncio.open_connection(**self.params)
        while True:
            line = await reader.readline()
            data = json.loads(line)
            match data:
                case {"LayerChange": {"new": name}}:
                    print("Active layer:", name)
                    self.viewer.focus(name)
                case {"ConfigFileReload": {"new": path}}:
                    print("Reload config")
                    self.viewer.hide()
                    self.renderer.load_config(Path(path))
                case _:
                    print("unknown message!", data)
