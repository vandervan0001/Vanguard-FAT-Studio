"""Generic OPC UA integration over real loopback sockets; NOT Siemens qualification."""

from dataclasses import dataclass
import hashlib

from asyncua import Server, ua
from asyncua.crypto.cert_gen import setup_self_signed_certificate
from cryptography.x509.oid import ExtendedKeyUsageOID
import pytest
import pytest_asyncio

from fat_studio.adapters.opcua import MappingError, OpcUaAdapter, PartialWriteError, VARIANT_TYPES
from fat_studio.models import PLCConfig, Project, Tag
from fat_studio.security import MachinePolicy, TargetDenied


APP_URI = "urn:fat-studio:generic-protocol-test"
NAMESPACE = "urn:fat-studio:test:exchange"


@dataclass
class Fixture:
    server: Server
    project: Project
    nodes: dict
    policy: MachinePolicy
    started: bool = True

    def adapter(self):
        plc = self.project.plc
        return OpcUaAdapter(self.project, self.policy, f"{plc.approved_virtual_target} @ {plc.endpoint}")

    async def stop(self):
        if self.started:
            await self.server.stop()
            self.started = False


async def build_fixture(tmp_path, port, *, encrypted=False):
    server = Server()
    await server.init()
    endpoint = f"opc.tcp://127.0.0.1:{port}/fat-test/"
    server.set_endpoint(endpoint)
    await server.set_application_uri(APP_URI)
    server.set_server_name("Generic OPC UA test double — not Siemens")
    namespace = await server.register_namespace(NAMESPACE)
    obj = await server.nodes.objects.add_object(namespace, "Exchange")
    nodes, tags = {}, []
    for direction in ("input", "output"):
        for kind, initial in (("BOOL", False), ("INT", 0), ("DINT", 0), ("REAL", 0.0)):
            tag_id = direction + "_" + kind.lower()
            node_id = ua.NodeId(tag_id, namespace)
            node = await obj.add_variable(node_id, tag_id, ua.Variant(initial, VARIANT_TYPES[kind]))
            if direction == "input":
                await node.set_writable()
            nodes[tag_id] = node
            tags.append(Tag(id=tag_id, name=tag_id, direction=direction, data_type=kind,
                            initial_value=initial, node_id=node_id.to_string(), writable=direction == "input"))
    plc = PLCConfig(mode="opcua", endpoint=endpoint, expected_application_uri=APP_URI,
                    approved_virtual_target="Generic OPC UA protocol fixture", namespace_uri=NAMESPACE, timeout_s=0.8)
    entry = {"endpoint": endpoint, "expected_application_uri": APP_URI,
             "approved_virtual_target": plc.approved_virtual_target, "isolated_virtual_adapter_confirmed": True,
             "allow_insecure": not encrypted, "server_certificate_sha256": ""}
    if encrypted:
        server_key, server_cert = tmp_path / "server-key.pem", tmp_path / "server.der"
        client_key, client_cert = tmp_path / "client-key.pem", tmp_path / "client.der"
        await setup_self_signed_certificate(server_key, server_cert, APP_URI, "localhost",
                                           [ExtendedKeyUsageOID.SERVER_AUTH], {"commonName": "Protocol fixture"})
        await setup_self_signed_certificate(client_key, client_cert, "urn:fat-studio:client", "localhost",
                                           [ExtendedKeyUsageOID.CLIENT_AUTH], {"commonName": "FAT Studio test client"})
        await server.load_certificate(server_cert)
        await server.load_private_key(server_key)
        server.set_security_policy([ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt])
        plc.security_policy = "Basic256Sha256"
        plc.client_certificate = str(client_cert)
        plc.client_private_key = str(client_key)
        plc.server_certificate_sha256 = hashlib.sha256(server_cert.read_bytes()).hexdigest()
        entry.update(server_certificate_sha256=plc.server_certificate_sha256,
                     client_certificate=str(client_cert), client_private_key=str(client_key))
    else:
        server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    project = Project(id="opcua-protocol-test", name="Generic OPC UA test", plc=plc, tags=tags)
    policy = MachinePolicy(tmp_path / "machine-policy.json")
    policy.add(entry)
    await server.start()
    return Fixture(server, project, nodes, policy)


@pytest_asyncio.fixture
async def fixture(tmp_path, unused_tcp_port):
    resource = await build_fixture(tmp_path, unused_tcp_port)
    try:
        yield resource
    finally:
        await resource.stop()


def values():
    return {"input_bool": True, "input_int": -32768, "input_dint": 2_147_483_647, "input_real": 12.5}


async def test_real_roundtrip_all_four_scalar_types(fixture):
    expected = {"output_bool": True, "output_int": 32767, "output_dint": -2_147_483_648, "output_real": 42.25}
    for key, value in expected.items():
        kind = next(tag.data_type for tag in fixture.project.tags if tag.id == key)
        await fixture.nodes[key].write_value(ua.Variant(value, VARIANT_TYPES[kind]))
    adapter = fixture.adapter()
    await adapter.connect()
    try:
        assert await adapter.read({}, 0.1) == expected
        await adapter.write(values())
        observed = {key: await fixture.nodes[key].read_value() for key in values()}
        assert observed == values()
        assert adapter.write_count == 4
        assert await fixture.nodes["output_int"].read_value() == 32767
    finally:
        await adapter.disconnect()


async def test_namespace_uri_resolves_stale_numeric_index(fixture):
    for tag in fixture.project.tags:
        tag.node_id = "ns=99;s=" + tag.id
    adapter = fixture.adapter()
    await adapter.connect()
    try:
        await adapter.write(values())
        assert await fixture.nodes["input_int"].read_value() == -32768
    finally:
        await adapter.disconnect()


@pytest.mark.parametrize("problem", ["missing", "type", "readonly", "array", "duplicate", "namespace"])
async def test_invalid_mapping_refused_before_any_write(fixture, problem):
    if problem == "missing":
        fixture.project.tags[0].node_id = "ns=2;s=does-not-exist"
    elif problem == "type":
        fixture.project.tags[0].node_id = fixture.project.tags[3].node_id
    elif problem == "readonly":
        await fixture.nodes["input_bool"].set_writable(False)
    elif problem == "array":
        await fixture.nodes["input_real"].write_value_rank(ua.ValueRank.OneDimension)
    elif problem == "duplicate":
        fixture.project.tags[4].node_id = "ns=99;s=input_bool"
    else:
        fixture.project.plc.namespace_uri = "urn:missing:namespace"
    adapter = fixture.adapter()
    with pytest.raises(MappingError):
        await adapter.connect()
    assert adapter.connected is False and adapter.write_count == 0
    assert await fixture.nodes["input_bool"].read_value() is False
    await adapter.disconnect()


async def test_unexpected_server_identity_refused(fixture):
    fixture.project.plc.expected_application_uri = "urn:wrong:identity"
    entry = fixture.policy.entries()[0]
    entry["expected_application_uri"] = "urn:wrong:identity"
    fixture.policy.add(entry)
    adapter = fixture.adapter()
    with pytest.raises(TargetDenied, match="ApplicationUri"):
        await adapter.connect()
    assert adapter.write_count == 0 and adapter.connected is False


async def test_target_confirmation_cannot_be_omitted(fixture):
    adapter = OpcUaAdapter(fixture.project, fixture.policy, None)
    with pytest.raises(TargetDenied, match="exactement"):
        await adapter.connect()
    assert adapter.client is None


async def test_whole_write_batch_validated_before_network_write(fixture):
    adapter = fixture.adapter()
    await adapter.connect()
    try:
        invalid = {**values(), "input_dint": 2_147_483_648}
        with pytest.raises(ValueError):
            await adapter.write(invalid)
        assert await fixture.nodes["input_bool"].read_value() is False
        assert adapter.write_count == 0 and adapter.connected is False
        with pytest.raises(ConnectionError):
            await adapter.write(values())
    finally:
        await adapter.disconnect()


async def test_output_variable_never_written(fixture):
    adapter = fixture.adapter()
    await adapter.connect()
    try:
        with pytest.raises(MappingError, match="exactement"):
            await adapter.write({**values(), "output_bool": True})
        assert await fixture.nodes["output_bool"].read_value() is False
        assert adapter.write_count == 0
    finally:
        await adapter.disconnect()


async def test_partial_server_write_latches_failure_and_preserves_status(fixture):
    adapter = fixture.adapter()
    await adapter.connect()
    # The server changes rights after validation. OPC UA batches are not atomic.
    await fixture.nodes["input_int"].set_writable(False)
    try:
        with pytest.raises(PartialWriteError) as error:
            await adapter.write(values())
        assert error.value.results["input_bool"] == "Good"
        assert error.value.results["input_int"] != "Good"
        assert set(error.value.results) == set(values())
        assert await fixture.nodes["input_bool"].read_value() is True
        assert await fixture.nodes["input_int"].read_value() == 0
        assert adapter.write_count == 3 and adapter.connected is False
        with pytest.raises(ConnectionError):
            await adapter.write(values())
    finally:
        await adapter.disconnect()


async def test_bad_quality_read_prevents_subsequent_write(fixture):
    adapter = fixture.adapter()
    await adapter.connect()
    try:
        bad = ua.DataValue(ua.Variant(False, ua.VariantType.Boolean), StatusCode_=ua.StatusCode(ua.StatusCodes.BadNoCommunication))
        await fixture.nodes["output_bool"].write_value(bad)
        with pytest.raises(ConnectionError, match="Qualité"):
            await adapter.read({}, 0.1)
        with pytest.raises(ConnectionError):
            await adapter.write(values())
        assert adapter.write_count == 0
    finally:
        await adapter.disconnect()


async def test_communication_loss_stops_writes_until_explicit_reconnect(fixture):
    adapter = fixture.adapter()
    await adapter.connect()
    await adapter.read({}, 0.1)
    await fixture.stop()
    try:
        with pytest.raises((ConnectionError, OSError, TimeoutError, ua.UaError)):
            await adapter.read({}, 0.1)
        assert adapter.connected is False
        with pytest.raises(ConnectionError):
            await adapter.write(values())
        assert adapter.write_count == 0
    finally:
        await adapter.disconnect()


async def test_sign_and_encrypt_with_real_pinned_certificate(tmp_path, unused_tcp_port):
    resource = await build_fixture(tmp_path, unused_tcp_port, encrypted=True)
    adapter = resource.adapter()
    try:
        await adapter.connect()
        await adapter.write(values())
        assert await resource.nodes["input_real"].read_value() == 12.5
        assert (await adapter.read({}, 0.1))["output_bool"] is False
    finally:
        await adapter.disconnect()
        await resource.stop()


async def test_wrong_certificate_pin_refuses_before_write(tmp_path, unused_tcp_port):
    resource = await build_fixture(tmp_path, unused_tcp_port, encrypted=True)
    resource.project.plc.server_certificate_sha256 = "f" * 64
    entry = resource.policy.entries()[0]
    resource.policy.add({**entry, "server_certificate_sha256": "f" * 64})
    adapter = resource.adapter()
    try:
        with pytest.raises(TargetDenied, match="certificat"):
            await adapter.connect()
        assert adapter.write_count == 0
    finally:
        await adapter.disconnect()
        await resource.stop()
