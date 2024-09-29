import subprocess
from i3ipc.aio import Connection
from i3ipc import Event


class KanataLayerViewer:
    def __init__(self, renderer, hidden_layers=[]):
        self.renderer = renderer
        self.process = None
        self.hidden_layers = hidden_layers

    async def run(self):
        async def on_output(conn, event):
            tree = await conn.get_tree()
            focused = tree.find_by_id(event.container.id)
            if not focused:
                return
            focused_output = focused.workspace().ipc_data["output"]
            try:
                (layer,) = [c for c in tree if c.app_id == "kanata-layer-viewer"]
            except ValueError:
                return
            layer_output = layer.workspace().ipc_data["output"]
            if focused_output == layer_output:
                await layer.command("move container to output right")
                await self.set_position(layer)

        async def on_new_window(conn, event):
            if event.container.app_id == "kanata-layer-viewer":
                await self.set_position(event.container)

        conn = await Connection(auto_reconnect=True).connect()
        conn.on(Event.WINDOW_FOCUS, on_output)
        conn.on(Event.WINDOW_NEW, on_new_window)

        await conn.main()

    async def set_position(self, c):
        await c.command("move position center")

    def focus(self, name):
        self.hide()
        if name in self.hidden_layers:
            return
        self.show(name)

    def hide(self):
        if self.process is None:
            return
        self.process.terminate()
        self.process = None

    def show(self, name):
        self.process = subprocess.Popen(
            [
                "swayimg",
                "--config", "viewer.transparency=#00000080",
                "--config", "general.app_id=kanata-layer-viewer",
                "--config", "viewer.scale=fit",
                "--config", "list.recursive=yes",
                "--config", "info.show=no",
                "--config", "general.size=1080,720",
                self.renderer.get_rendered_layer_path(name),
            ],
        )
