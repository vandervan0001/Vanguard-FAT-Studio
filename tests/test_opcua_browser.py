"""Real loopback OPC UA metadata tests; these do not qualify a Siemens target."""

import asyncio
import struct

from asyncua import ua
from asyncua.server.internal_session import InternalSession
from asyncua.ua.ua_binary import uatcp_to_binary
import httpx
import pytest

from fat_studio.adapters.opcua import IdentityClient, MappingError
from fat_studio.app import create_app
from fat_studio.opcua_browser import MetadataBrowser, MetadataIdentityClient, browse_metadata
from fat_studio.models import Project
from fat_studio.security import MachinePolicy
from fat_studio.security import TargetDenied
from test_opcua import build_fixture


def confirmation(project):
    return f"{project.plc.approved_virtual_target} @ {project.plc.endpoint}"


@pytest.mark.parametrize("node_id", ["invalid", "ns=wrong;i=12", "i=2253", "svr=1;ns=2;i=42", "nsu=urn:other;i=42", "ns=65536;i=1", "ns=1;i=4294967296"])
async def test_invalid_or_external_parent_is_refused_without_connection(tmp_path, node_id, monkeypatch):
    project = Project(id="browse", name="Browse")
    project.plc.mode = "opcua"

    async def unexpected_connection(*args, **kwargs):
        raise AssertionError("No transport may open for this parent")

    monkeypatch.setattr(MetadataBrowser, "connect", unexpected_connection)
    with pytest.raises(MappingError):
        await browse_metadata(project, MachinePolicy(tmp_path / "none.json"), "unused", node_id)


async def test_hostile_ack_and_incomplete_large_packet_cannot_remove_browser_limits(unused_tcp_port):
    release_packet = asyncio.Event()
    server_finished = asyncio.Event()

    async def hostile_peer(reader, writer):
        try:
            await reader.read(65535)  # HEL from the real asyncua client.
            ack = ua.Acknowledge()
            ack.ReceiveBufferSize = 2 ** 31
            ack.SendBufferSize = 2 ** 31
            ack.MaxChunkCount = 0
            ack.MaxMessageSize = 0
            writer.write(uatcp_to_binary(ua.MessageType.Acknowledge, ack))
            await writer.drain()
            await release_packet.wait()
            await reader.read(65535)  # OpenSecureChannel request.
            # A declared 16 MiB packet that never completes, streamed in pieces.
            writer.write(struct.pack("<3scII", b"OPN", b"F", 16 * 1024 * 1024, 0))
            for _ in range(20):
                writer.write(b"x" * 65535)
                await writer.drain()
                await asyncio.sleep(0)
        except (ConnectionError, BrokenPipeError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, BrokenPipeError):
                pass
            server_finished.set()

    server = await asyncio.start_server(hostile_peer, "127.0.0.1", unused_tcp_port)
    client = MetadataIdentityClient(f"opc.tcp://127.0.0.1:{unused_tcp_port}", timeout=1,
                                    identity_check=lambda *_: None)
    try:
        await client.connect_socket()
        await client.send_hello()
        protocol = client.uaclient.protocol
        limits = protocol._connection._limits
        assert 0 < limits.max_recv_buffer <= 65535
        assert 0 < limits.max_chunk_count <= 64
        assert 0 < limits.max_message_size <= 4 * 1024 * 1024
        assert not limits.is_chunk_count_within_limit(65)
        release_packet.set()
        with pytest.raises(MappingError, match="volumineuse"):
            await client.open_secure_channel()
        assert protocol.receive_buffer is None
    finally:
        client.disconnect_socket()
        release_packet.set()
        server.close()
        await server.wait_closed()
        await asyncio.wait_for(server_finished.wait(), 3)


async def test_real_browse_reports_exact_scalar_types_rights_and_never_writes(tmp_path, unused_tcp_port, monkeypatch):
    resource = await build_fixture(tmp_path, unused_tcp_port)
    namespace = await resource.server.get_namespace_index(resource.project.plc.namespace_uri)
    objects = await resource.server.nodes.objects.get_children()
    exchange = next(node for node in objects if node.nodeid.NamespaceIndex == namespace)
    array = await exchange.add_variable(ua.NodeId("array", namespace), "Array", ua.Variant([1.0, 2.0], ua.VariantType.Float))
    await array.write_value_rank(ua.ValueRank.OneDimension)
    await exchange.add_variable(ua.NodeId("double", namespace), "Double", ua.Variant(0.0, ua.VariantType.Double))
    writes = []
    original = InternalSession.write

    async def observed_write(session, params):
        writes.extend(params.NodesToWrite)
        return await original(session, params)

    monkeypatch.setattr(InternalSession, "write", observed_write)
    # Missing mappings are expected during discovery; they never grant a write session.
    for tag in resource.project.tags:
        tag.node_id = ""
    try:
        root = await browse_metadata(resource.project, resource.policy, confirmation(resource.project))
        folder = next(node for node in root["nodes"] if node["name"] == "Exchange")
        assert folder["kind"] == "object"
        assert next(node for node in root["nodes"] if node["name"] == "Server")["reason"]
        page = await browse_metadata(resource.project, resource.policy, confirmation(resource.project), folder["node_id"])
        rows = {node["name"]: node for node in page["nodes"]}
        for direction in ("input", "output"):
            for kind in ("BOOL", "INT", "DINT", "REAL"):
                row = rows[direction + "_" + kind.lower()]
                assert row["data_type"] == kind and row["readable"] and row["selectable"]
                assert row["writable"] is (direction == "input")
        assert not rows["Array"]["selectable"] and "Tableaux" in rows["Array"]["reason"]
        assert not rows["Double"]["selectable"] and rows["Double"]["data_type"] is None
        assert writes == []
        assert await resource.nodes["input_bool"].read_value() is False
        assert await resource.nodes["input_real"].read_value() == 0.0
        browser = MetadataBrowser(resource.project, resource.policy, confirmation(resource.project))
        with pytest.raises(MappingError, match="lecture seule"):
            await browser.write({"input_bool": True})
    finally:
        await resource.stop()


async def test_browse_pages_are_bounded_and_namespace_zero_is_never_selectable(tmp_path, unused_tcp_port):
    resource = await build_fixture(tmp_path, unused_tcp_port)
    namespace = await resource.server.get_namespace_index(resource.project.plc.namespace_uri)
    folder = await resource.server.nodes.objects.add_object(namespace, "Many variables")
    for index in range(105):
        await folder.add_variable(ua.NodeId(f"many-{index}", namespace), f"Signal {index}", ua.Variant(0, ua.VariantType.Int16))
    try:
        first = await browse_metadata(resource.project, resource.policy, confirmation(resource.project), folder.nodeid.to_string())
        second = await browse_metadata(resource.project, resource.policy, confirmation(resource.project), folder.nodeid.to_string(), 100)
        assert len(first["nodes"]) == 100 and first["more"]
        assert len(second["nodes"]) == 5 and not second["more"]
        assert not ({row["node_id"] for row in first["nodes"]} & {row["node_id"] for row in second["nodes"]})
        with pytest.raises(MappingError, match="système"):
            await browse_metadata(resource.project, resource.policy, confirmation(resource.project), "i=2253")
        with pytest.raises(MappingError, match="Page"):
            await browse_metadata(resource.project, resource.policy, confirmation(resource.project), offset=1)
        resource.project.plc.namespace_uri = "http://opcfoundation.org/UA/"
        with pytest.raises(MappingError, match="système 0"):
            await browse_metadata(resource.project, resource.policy, confirmation(resource.project))
    finally:
        await resource.stop()


async def test_browse_checks_actual_identity_before_session_activation(tmp_path, unused_tcp_port, monkeypatch):
    resource = await build_fixture(tmp_path, unused_tcp_port)
    resource.project.plc.expected_application_uri = "urn:wrong-identity"
    policy = resource.policy.entries()[0]
    policy["expected_application_uri"] = "urn:wrong-identity"
    resource.policy.add(policy)
    activated = []
    original = IdentityClient.activate_session

    async def activate(client, *args, **kwargs):
        activated.append(True)
        return await original(client, *args, **kwargs)

    monkeypatch.setattr(IdentityClient, "activate_session", activate)
    try:
        with pytest.raises(TargetDenied, match="ApplicationUri"):
            await browse_metadata(resource.project, resource.policy, confirmation(resource.project))
        assert activated == []
        with pytest.raises(TargetDenied, match="Confirmer"):
            await browse_metadata(resource.project, resource.policy, "another target")
        assert activated == []
    finally:
        await resource.stop()


async def test_encrypted_metadata_browse_uses_pinned_certificate(tmp_path, unused_tcp_port):
    resource = await build_fixture(tmp_path, unused_tcp_port, encrypted=True)
    try:
        result = await browse_metadata(resource.project, resource.policy, confirmation(resource.project))
        assert any(node["name"] == "Exchange" for node in result["nodes"])
        resource.project.plc.server_certificate_sha256 = "0" * 64
        entry = resource.policy.entries()[0]
        entry["server_certificate_sha256"] = "0" * 64
        resource.policy.add(entry)
        with pytest.raises(TargetDenied, match="certificat"):
            await browse_metadata(resource.project, resource.policy, confirmation(resource.project))
        assert await resource.nodes["input_bool"].read_value() is False
    finally:
        await resource.stop()


async def test_api_real_browse_keeps_draft_and_runtime_idle(tmp_path, unused_tcp_port):
    resource = await build_fixture(tmp_path / "ua", unused_tcp_port)
    app = create_app(tmp_path / "app")
    try:
        async with app.router.lifespan_context(app):
            app.state.policy.add(resource.policy.entries()[0])
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
                response = await client.get("/api/project")
                original = response.json()
                draft = resource.project.model_dump(mode="json")
                draft["id"] = original["id"]
                headers = {"X-FAT-Token": (await client.get("/api/session")).json()["token"],
                           "X-FAT-Project-ID": draft["id"], "X-FAT-Project-Revision": response.headers["X-FAT-Project-Revision"], "X-FAT-Run-ID": ""}
                body = {"project": draft, "confirmation": confirmation(resource.project)}
                result = await client.post("/api/opcua/browse", json=body, headers=headers)
                assert result.status_code == 200, result.text
                assert any(node["name"] == "Exchange" for node in result.json()["nodes"])
                assert (await client.get("/api/project")).json() == original
                state = (await client.get("/api/state")).json()
                assert state["run_id"] is None and state["status"] == "idle" and state["write_count"] == 0
                headers["X-FAT-Project-Revision"] = "old-revision"
                assert (await client.post("/api/opcua/browse", json=body, headers=headers)).status_code == 409
    finally:
        await resource.stop()
