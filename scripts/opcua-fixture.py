#!/usr/bin/env python3
"""Run a generic loopback OPC UA controller fixture, without Siemens or process physics.

This is a protocol test double, not a PLCSIM emulator or Siemens qualification.
The FAT application supplies the process model; this process supplies only the
demonstration controller, reading its sensors and producing PLC command tags.
It never creates a machine authorization or connects to another OPC UA server.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys
import time

# Permit the documented repository command before an editable package install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from asyncua import Server, ua  # noqa: E402
from fat_studio.adapters.opcua import VARIANT_TYPES  # noqa: E402
from fat_studio.demo import demo_project  # noqa: E402
from fat_studio.engine import DemoController  # noqa: E402
from fat_studio.models import PLCConfig  # noqa: E402
from fat_studio.security import atomic_json  # noqa: E402
from fat_studio.pilot import PilotController, pilot_project  # noqa: E402


APPLICATION_URI = "urn:fat-studio:generic-opcua-fixture"
NAMESPACE_URI = "urn:fat-studio:fixture:DB_FAT"
TARGET_NAME = "Generic OPC UA fixture"


async def run(args):
    server = Server()
    await server.init()
    endpoint = f"opc.tcp://127.0.0.1:{args.port}/fat-fixture/"
    server.set_endpoint(endpoint)
    server.set_server_name("Vanguard FAT Studio generic test controller — not Siemens")
    await server.set_application_uri(APPLICATION_URI)
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    # No non-loopback address or remote endpoint option is offered.
    namespace = await server.register_namespace(NAMESPACE_URI)
    exchange = await server.nodes.objects.add_object(namespace, "DB_FAT")
    pilot = getattr(args, "controller", "tank") == "standard-pilot"
    project = pilot_project() if pilot else demo_project()
    project.id = "opcua-fixture"
    project.name = "PILOTE-01 · OPC UA générique" if pilot else "TK-101 · Test OPC UA générique"
    project.description = (
        "Test de protocole générique sur 127.0.0.1 ; ne constitue pas une qualification Siemens. "
        "Le serveur scripts/opcua-fixture.py exécute seulement le contrôleur fictif à 100 ms. "
        "Vanguard FAT Studio exécute le procédé et écrit les entrées simulées. Arrêter le serveur permet "
        "de vérifier le traitement d'une perte de communication."
    )
    project.plc = PLCConfig(mode="opcua", endpoint=endpoint, expected_application_uri=APPLICATION_URI,
                            namespace_uri=NAMESPACE_URI, approved_virtual_target=TARGET_NAME)
    nodes = {}
    for tag in project.tags:
        nodeid = ua.NodeId(tag.id, namespace)
        node = await exchange.add_variable(nodeid, tag.name, ua.Variant(tag.initial_value, VARIANT_TYPES[tag.data_type]))
        if tag.direction == "input":
            await node.set_writable()
        tag.node_id = nodeid.to_string()
        nodes[tag.id] = node
    controller = PilotController(project) if pilot else DemoController(project)
    inputs = [tag for tag in project.tags if tag.direction == "input"]
    outputs = [tag for tag in project.tags if tag.direction == "output"]
    target_confirmation = f"{TARGET_NAME} @ {endpoint}"
    metadata = {
        "qualification": "generic_opcua_protocol_only_not_siemens", "endpoint": endpoint,
        "application_uri": APPLICATION_URI, "namespace_uri": NAMESPACE_URI,
        "project_file": str(args.project.resolve()), "tag_count": len(project.tags),
        "controller_period_ms": 100, "confirmation": target_confirmation,
        "machine_policy_modified": False,
    }
    async with server:
        atomic_json(args.project, project.model_dump(mode="json"))
        if args.ready_file:
            atomic_json(args.ready_file, metadata)
        print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
        print("\nServeur de test générique démarré ; aucun logiciel Siemens connecté.", flush=True)
        print("Autorisation explicite à exécuter dans un autre terminal (même --data-dir que l'application) :", flush=True)
        print(f'vanguard-fat-studio authorize-target --endpoint "{endpoint}" --application-uri "{APPLICATION_URI}" '
              f'--name "{TARGET_NAME}" --isolated-virtual-adapter --allow-insecure', flush=True)
        print("Confirmer : " + target_confirmation, flush=True)
        print("Importer ensuite le JSON généré dans Vanguard FAT Studio, puis lancer le scénario de référence à 1×.", flush=True)
        print("Ctrl+C arrête ce serveur pour tester la perte de communication.", flush=True)
        began = time.monotonic()
        deadline = began
        while args.duration <= 0 or time.monotonic() - began < args.duration:
            sensed = {tag.id: await nodes[tag.id].read_value() for tag in inputs}
            commands = controller.read_commands(sensed, 0.1)
            for tag in outputs:
                await nodes[tag.id].write_value(ua.Variant(commands[tag.id], VARIANT_TYPES[tag.data_type]))
            deadline += 0.1
            await asyncio.sleep(max(0.001, deadline - time.monotonic()))
            if deadline < time.monotonic() - 0.1:
                deadline = time.monotonic()
    print("Serveur OPC UA de test arrêté.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=48450)
    parser.add_argument("--controller", choices=("tank", "standard-pilot"), default="tank")
    parser.add_argument("--project", type=Path, default=Path(".local/opcua-fixture.project.json"))
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--duration", type=float, default=0, help="Stop after this many seconds; 0 runs until Ctrl+C.")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or args.duration < 0:
        parser.error("Port must be 1–65535 and duration must be nonnegative.")
    logging.basicConfig(level=logging.ERROR)
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("Serveur OPC UA de test arrêté.")


if __name__ == "__main__":
    main()
