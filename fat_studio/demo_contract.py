"""Public laboratory I/O contract. No customer programming standard or process sequence."""
from __future__ import annotations

DEMO_VERSION = "1.0"
DB_NAME = "DB_FAT_Demo"

TANKS = [
    dict(id="TK101", name="TK-101 · Alimentation", capacity_l=1200.0, initial_level_pct=60.0, x=240.0, y=100.0),
    dict(id="TK201", name="TK-201 · Cuve intermédiaire", capacity_l=1800.0, initial_level_pct=25.0, x=780.0, y=100.0),
    dict(id="TK301", name="TK-301 · Réception", capacity_l=1200.0, initial_level_pct=15.0, x=1320.0, y=100.0),
]
PUMPS = [
    dict(id="P101", name="P-101 · Alimentation", tank_id="TK101", role="inlet", source_tank_id="", flow_group="fill101", max_flow_l_s=35.0, x=0.0, y=350.0),
    dict(id="P201", name="P-201 · Transfert 1", tank_id="TK201", role="inlet", source_tank_id="TK101", flow_group="transfer201", max_flow_l_s=30.0, x=500.0, y=350.0),
    dict(id="P202", name="P-202 · Transfert 2", tank_id="TK301", role="inlet", source_tank_id="TK201", flow_group="transfer202", max_flow_l_s=26.0, x=1040.0, y=350.0),
    dict(id="P301", name="P-301 · Vidange", tank_id="TK301", role="outlet", source_tank_id="", flow_group="drain301", max_flow_l_s=20.0, x=1560.0, y=350.0),
]
VALVES = [
    dict(id="XV101", name="XV-101 · Arrivée", tank_id="TK101", role="inlet", flow_group="fill101", max_flow_l_s=45.0, x=240.0, y=350.0),
    dict(id="XV201", name="XV-201 · Transfert 1", tank_id="TK201", role="inlet", flow_group="transfer201", max_flow_l_s=40.0, x=780.0, y=350.0),
    dict(id="XV202", name="XV-202 · Transfert 2", tank_id="TK301", role="inlet", flow_group="transfer202", max_flow_l_s=35.0, x=1320.0, y=350.0),
    dict(id="XV301", name="XV-301 · Sortie", tank_id="TK301", role="outlet", flow_group="drain301", max_flow_l_s=30.0, x=1560.0, y=560.0),
    dict(id="XV102", name="XV-102 · Purge source", tank_id="TK101", role="outlet", flow_group="drain101", max_flow_l_s=14.0, x=240.0, y=560.0),
    dict(id="XV203", name="XV-203 · Purge intermédiaire", tank_id="TK201", role="outlet", flow_group="drain201", max_flow_l_s=14.0, x=780.0, y=560.0),
    dict(id="XV103", name="XV-103 · Évent illustratif", tank_id="TK101", role="inlet", flow_group="vent101", max_flow_l_s=0.0, x=0.0, y=210.0),
    dict(id="FCV302", name="FCV-302 · Réglage sortie", tank_id="TK301", role="outlet", flow_group="drain301", max_flow_l_s=30.0, x=1320.0, y=560.0),
]

# tag_id -> (PLC field, direction viewed from PLC, type, initial value, unit, low, high).
# Requests are simulated operator inputs. Only PLC command outputs actuate the plant.
DEMO_TAGS: dict[str, tuple] = {
    "stop_healthy": ("StopHealthy", "input", "BOOL", True, "", None, None),
}
for pump in PUMPS:
    prefix = pump["id"].lower()
    for suffix, field, direction, kind, value, unit, low, high in [
        ("request", "Request", "input", "BOOL", False, "", None, None),
        ("requested_speed", "RequestedSpeed", "input", "REAL", 60.0, "%", 0.0, 100.0),
        ("command", "RunCommand", "output", "BOOL", False, "", None, None),
        ("speed_command", "SpeedCommand", "output", "REAL", 0.0, "%", 0.0, 100.0),
        ("running", "Running", "input", "BOOL", False, "", None, None),
        ("speed", "SpeedFeedback", "input", "REAL", 0.0, "%", 0.0, 100.0),
        ("fault", "Fault", "input", "BOOL", False, "", None, None),
    ]:
        DEMO_TAGS[f"{prefix}_{suffix}"] = (f"{pump['id']}_{field}", direction, kind, value, unit, low, high)
for valve in VALVES:
    prefix = valve["id"].lower()
    if valve["id"].startswith("FCV"):
        definitions = [("request", "RequestedPosition", "input", "REAL", 0.0, "%", 0.0, 100.0),
                       ("command", "PositionCommand", "output", "REAL", 0.0, "%", 0.0, 100.0),
                       ("position", "PositionFeedback", "input", "REAL", 0.0, "%", 0.0, 100.0)]
    else:
        definitions = [("request", "Request", "input", "BOOL", False, "", None, None),
                       ("command", "OpenCommand", "output", "BOOL", False, "", None, None),
                       ("open", "Open", "input", "BOOL", False, "", None, None),
                       ("closed", "Closed", "input", "BOOL", True, "", None, None)]
    for suffix, field, direction, kind, value, unit, low, high in definitions:
        DEMO_TAGS[f"{prefix}_{suffix}"] = (f"{valve['id']}_{field}", direction, kind, value, unit, low, high)
for tank in TANKS:
    number = tank["id"][2:]
    prefix = f"lt{number}"
    DEMO_TAGS[f"{prefix}_raw"] = (f"LT{number}_Raw", "input", "INT", round(tank["initial_level_pct"] * 276.48), "counts", 0, 27648)
    DEMO_TAGS[f"{prefix}_percent"] = (f"LT{number}_Percent", "output", "REAL", 0.0, "%", None, None)
    DEMO_TAGS[f"tk{number}_volume"] = (f"TK{number}_Volume", "input", "REAL", tank["capacity_l"] * tank["initial_level_pct"] / 100, "L", 0.0, tank["capacity_l"])
    DEMO_TAGS[f"lsl{number}"] = (f"LSL{number}", "input", "BOOL", False, "", None, None)
    DEMO_TAGS[f"lsh{number}"] = (f"LSH{number}", "input", "BOOL", False, "", None, None)
