from __future__ import annotations

from ..engine import DemoController


class DemoAdapter:
    """Demonstration controller, used only when the project explicitly selects demo."""

    def __init__(self, project):
        if project.plc.demo_controller == "manual_lab_v1":
            from ..demo_lab import ManualLabController
            self.controller = ManualLabController(project)
            self.target = "Laboratoire I/O passif · référence Python explicite, aucun PLC connecté"
        else:
            self.controller = DemoController(project)
            self.target = "Contrôleur de démonstration local — aucun PLC connecté"
        self.connected = False
        self.write_count = 0

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def read(self, values: dict, dt: float) -> dict:
        if not self.connected:
            raise ConnectionError("Contrôleur de démonstration déconnecté.")
        return self.controller.read_commands(values, dt)

    async def write(self, values: dict) -> None:
        if not self.connected:
            raise ConnectionError("Contrôleur de démonstration déconnecté.")
        self.write_count += len(values)

