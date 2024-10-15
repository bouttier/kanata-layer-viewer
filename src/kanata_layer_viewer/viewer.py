import subprocess
from i3ipc.aio import Connection
from i3ipc import Event


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
