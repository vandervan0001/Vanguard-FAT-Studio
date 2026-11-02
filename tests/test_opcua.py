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


async def build_fixture(tmp_path, port, *, encrypted=False, server_certificate_transform=None):
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
        if server_certificate_transform:
            server_certificate_transform(server_key, server_cert)
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


async def test_namespace_resolution_cannot_bypass_system_namespace_prohibition(fixture):
    node = await fixture.server.nodes.objects.add_variable(
        ua.NodeId("unsafe_system_write", 0), "UnsafeSystemWrite", ua.Variant(0., ua.VariantType.Float))
    await node.set_writable()
    fixture.project.plc.namespace_uri = "http://opcfoundation.org/UA/"
    fixture.project.tags = [Tag(id="signal", name="Signal", direction="input", data_type="REAL",
                                initial_value=0., writable=True, node_id="ns=2;s=unsafe_system_write")]
    adapter = fixture.adapter()
    try:
        with pytest.raises(MappingError, match="système 0"):
            await adapter.connect()
        assert adapter.write_count == 0
        assert await node.read_value() == 0.
    finally:
        await adapter.disconnect()


async def test_model_evidence_matches_real_float32_roundtrip(fixture):
    from fat_studio.engine import ProcessEngine

    tag = next(tag for tag in fixture.project.tags if tag.id == "input_real")
    tag.initial_value = 16_777_217.
    engine = ProcessEngine(fixture.project)
    adapter = fixture.adapter()
    try:
        await adapter.connect()
        image = engine.step(await adapter.read(engine.values, .1), .1)
        await adapter.write(image)
        assert engine.values["input_real"] == await fixture.nodes["input_real"].read_value()
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


@pytest.mark.parametrize("problem", ["expired", "future", "uri"])
async def test_pinned_certificate_still_requires_valid_time_and_application_uri(tmp_path, unused_tcp_port, problem):
    from datetime import datetime, timedelta, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization

    def transform(key_path, cert_path):
        cert = x509.load_der_x509_certificate(cert_path.read_bytes())
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        now = datetime.now(timezone.utc)
        before = now + timedelta(days=1) if problem == "future" else now - timedelta(days=2)
        after = now - timedelta(days=1) if problem == "expired" else now + timedelta(days=2)
        builder = (x509.CertificateBuilder().subject_name(cert.subject).issuer_name(cert.issuer)
                   .public_key(cert.public_key()).serial_number(cert.serial_number)
                   .not_valid_before(before).not_valid_after(after))
        for extension in cert.extensions:
            value = extension.value
            if problem == "uri" and isinstance(value, x509.SubjectAlternativeName):
                value = x509.SubjectAlternativeName([x509.UniformResourceIdentifier("urn:wrong:certificate:identity"),
                                                    x509.DNSName("localhost")])
            builder = builder.add_extension(value, critical=extension.critical)
        cert_path.write_bytes(builder.sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.DER))

    resource = await build_fixture(tmp_path, unused_tcp_port, encrypted=True, server_certificate_transform=transform)
    adapter = resource.adapter()
    try:
        with pytest.raises(ua.UaError):
            await adapter.connect()
        assert not adapter.connected and adapter.write_count == 0
        assert await resource.nodes["input_bool"].read_value() is False
    finally:
        await adapter.disconnect()
        await resource.stop()


async def test_session_identity_is_checked_before_user_authentication(tmp_path, unused_tcp_port, monkeypatch):
    import copy
    from asyncua.server.internal_session import InternalSession
    from fat_studio.adapters.opcua import IdentityClient

    resource = await build_fixture(tmp_path, unused_tcp_port, encrypted=True)
    resource.project.plc.username_env = "FAT_TEST_USER"
    resource.project.plc.password_env = "FAT_TEST_PASSWORD"
    resource.policy.add({**resource.policy.entries()[0], "username_env": "FAT_TEST_USER", "password_env": "FAT_TEST_PASSWORD"})
    monkeypatch.setenv("FAT_TEST_USER", "fixture-user")
    monkeypatch.setenv("FAT_TEST_PASSWORD", "fixture-test-only-password")
    original_session = InternalSession.create_session
    original_activate = IdentityClient.activate_session
    authentication_attempts = []

    async def changed_session_identity(session, *args, **kwargs):
        response = await original_session(session, *args, **kwargs)
        response.ServerEndpoints = copy.deepcopy(response.ServerEndpoints)
        for endpoint in response.ServerEndpoints:
            endpoint.Server.ApplicationUri = "urn:session:identity:changed"
        return response

    async def observe_authentication(client, *args, **kwargs):
        authentication_attempts.append(bool(kwargs.get("username")))
        return await original_activate(client, *args, **kwargs)

    monkeypatch.setattr(InternalSession, "create_session", changed_session_identity)
    monkeypatch.setattr(IdentityClient, "activate_session", observe_authentication)
    adapter = resource.adapter()
    try:
        with pytest.raises((TargetDenied, ua.UaError)):
            await adapter.connect()
        assert authentication_attempts == [], "Credentials must not be sent before the actual session identity is accepted"
        assert not adapter.connected and adapter.write_count == 0
    finally:
        await adapter.disconnect()
        await resource.stop()


@pytest.mark.parametrize("credential", ["correct", "wrong", "missing"])
async def test_encrypted_user_authentication_and_failure_have_no_fallback(tmp_path, unused_tcp_port, monkeypatch, credential):
    from asyncua.crypto.permission_rules import User, UserRole

    resource = await build_fixture(tmp_path, unused_tcp_port, encrypted=True)
    resource.project.plc.username_env = "FAT_TEST_USER"
    resource.project.plc.password_env = "FAT_TEST_PASSWORD"
    resource.policy.add({**resource.policy.entries()[0], "username_env": "FAT_TEST_USER", "password_env": "FAT_TEST_PASSWORD"})
    monkeypatch.setenv("FAT_TEST_USER", "fixture-user")
    monkeypatch.delenv("FAT_TEST_PASSWORD", raising=False)
    if credential != "missing":
        monkeypatch.setenv("FAT_TEST_PASSWORD", "fixture-password" if credential == "correct" else "incorrect-password")

    class RequiredUser:
        def get_user(self, iserver, username=None, password=None, certificate=None):
            return User(role=UserRole.User) if username == "fixture-user" and password == "fixture-password" else None

    resource.server.iserver.user_manager = RequiredUser()
    adapter = resource.adapter()
    try:
        if credential == "correct":
            await adapter.connect()
            await adapter.write(values())
            assert await resource.nodes["input_real"].read_value() == 12.5
        else:
            with pytest.raises((TargetDenied, ua.UaError)):
                await adapter.connect()
            assert not adapter.connected and adapter.write_count == 0
            assert await resource.nodes["input_bool"].read_value() is False
            with pytest.raises(ConnectionError):
                await adapter.write(values())
    finally:
        await adapter.disconnect()
        await resource.stop()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), [1., 2.]])
async def test_invalid_live_real_image_latches_session_before_any_write(fixture, value):
    adapter = fixture.adapter()
    try:
        await adapter.connect()
        await fixture.nodes["output_real"].write_value(ua.Variant(value, ua.VariantType.Float))
        with pytest.raises(ValueError, match="REAL fini"):
            await adapter.read({}, .1)
        assert not adapter.connected
        with pytest.raises(ConnectionError):
            await adapter.write(values())
        assert adapter.write_count == 0
        assert await fixture.nodes["input_bool"].read_value() is False
    finally:
        await adapter.disconnect()


async def test_cancelled_disconnect_always_closes_owned_transport(tmp_path):
    import asyncio

    entered = asyncio.Event()

    class SuspendedClient:
        closed = False

        async def disconnect(self):
            entered.set()
            await asyncio.Event().wait()

        def disconnect_socket(self):
            self.closed = True

    project = Project(id="cancel", name="Cancel cleanup")
    adapter = OpcUaAdapter(project, MachinePolicy(tmp_path / "unused-policy.json"), "unused")
    client = SuspendedClient()
    adapter.client, adapter.connected = client, True
    task = asyncio.create_task(adapter.disconnect())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert client.closed
    assert adapter.client is None and not adapter.connected
