"""OPC UA adapter backed by FreeOpcUa asyncua; no S7 protocol is reimplemented."""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

from asyncua import Client, ua
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from asyncua.crypto.validator import CertificateValidator, CertificateValidatorOptions

from ..branding import APP_NAME
from ..models import validate_tag_value
from ..security import MachinePolicy, TargetDenied


VARIANT_TYPES = {"BOOL": ua.VariantType.Boolean, "INT": ua.VariantType.Int16,
                 "DINT": ua.VariantType.Int32, "REAL": ua.VariantType.Float}


class MappingError(ValueError):
    pass


class PartialWriteError(ConnectionError):
    def __init__(self, results: dict):
        self.results = results
        super().__init__(f"Écriture OPC UA partielle/refusée : {results}. L'essai est arrêté, sans reprise automatique.")


class IdentityClient(Client):
    """Retain identity from the actual CreateSession response, not a display label."""

    def __init__(self, *args, identity_check, **kwargs):
        super().__init__(*args, **kwargs)
        self._identity_check = identity_check

    async def create_session(self):
        response = await super().create_session()
        selected = self.find_endpoint(response.ServerEndpoints, self.security_policy.Mode, self.security_policy.URI)
        self.server_application_uri = selected.Server.ApplicationUri
        # Client.connect activates the session immediately after this method.
        # Check here, before user credentials can leave the client.
        self._identity_check(self.server_application_uri, self.security_policy.peer_certificate)
        return response


class OpcUaAdapter:
    def __init__(self, project, policy: MachinePolicy, confirmation: str):
        self.project = project
        self.config = project.plc
        self.policy = policy
        self.confirmation = confirmation
        self.client: IdentityClient | None = None
        self.nodes = {}
        self.tags = {tag.id: tag for tag in project.tags}
        self.input_ids = [tag.id for tag in project.tags if tag.direction == "input" and tag.writable]
        self.output_ids = [tag.id for tag in project.tags if tag.direction == "output"]
        self.connected = False
        self.write_count = 0
        self.target = f"{self.config.approved_virtual_target} @ {self.config.endpoint}"

    def _create_client(self) -> IdentityClient:
        return IdentityClient(self.config.endpoint, timeout=self.config.timeout_s, identity_check=self._check_identity)

    def _check_identity(self, application_uri: str, certificate: bytes | None) -> None:
        if application_uri != self.config.expected_application_uri:
            raise TargetDenied(f"ApplicationUri serveur inattendue : {application_uri!r}. Aucune écriture effectuée.")
        expected = self.config.server_certificate_sha256.lower().replace(":", "")
        if expected:
            actual = hashlib.sha256(certificate or b"").hexdigest()
            if actual != expected:
                raise TargetDenied("Empreinte du certificat serveur inattendue. Aucune écriture effectuée.")

    async def connect(self) -> None:
        # Re-read local policy on every connection; an imported project cannot authorize itself.
        if self.connected or self.client is not None:
            await self.disconnect()
        if self.confirmation != self.target:
            raise TargetDenied(f"Confirmer exactement la cible : {self.target}")
        self.policy.authorize(self.config, self.confirmation)
        self.nodes.clear()
        client = self._create_client()
        client.application_uri = "urn:fat-studio:client"
        client.name = f"{APP_NAME} local virtual-PLC test client"
        self.client = client
        try:
            async with asyncio.timeout(self.config.timeout_s * 5):
                if self.config.security_policy == "Basic256Sha256":
                    # Fingerprint pinning establishes trust in this certificate;
                    # its validity window and application identity still apply.
                    client.certificate_validator = CertificateValidator(
                        CertificateValidatorOptions.TIME_RANGE | CertificateValidatorOptions.URI
                        | CertificateValidatorOptions.PEER_SERVER)
                    for name in ("client_certificate", "client_private_key"):
                        if not Path(getattr(self.config, name)).is_file():
                            raise TargetDenied(f"Fichier {name} manquant sur le poste.")
                    endpoints = await client.connect_and_get_server_endpoints()
                    endpoint = Client.find_endpoint(endpoints, ua.MessageSecurityMode.SignAndEncrypt,
                                                    SecurityPolicyBasic256Sha256.URI)
                    self._check_identity(endpoint.Server.ApplicationUri, endpoint.ServerCertificate)
                    await client.set_security(
                        SecurityPolicyBasic256Sha256, self.config.client_certificate,
                        self.config.client_private_key, server_certificate=endpoint.ServerCertificate,
                        mode=ua.MessageSecurityMode.SignAndEncrypt,
                    )
                if self.config.username_env or self.config.password_env:
                    if self.config.security_policy == "None":
                        raise TargetDenied(f"Les identifiants OPC UA exigent SignAndEncrypt dans {APP_NAME}.")
                    username = os.environ.get(self.config.username_env, "")
                    password = os.environ.get(self.config.password_env, "")
                    if not username or not password:
                        raise TargetDenied("Variables d'environnement des identifiants OPC UA absentes.")
                    client.set_user(username)
                    client.set_password(password)
                await client.connect()
                self._check_identity(client.server_application_uri, client.security_policy.peer_certificate)
                await self._validate_nodes()
            self.connected = True
        except BaseException as error:
            try:
                await self.disconnect()
            except Exception as cleanup_error:
                error.add_note(f"Échec de fermeture de la session OPC UA : {cleanup_error}")
            raise

    async def _validate_nodes(self) -> None:
        assert self.client is not None
        namespace = None
        if self.config.namespace_uri:
            try:
                namespace = await self.client.get_namespace_index(self.config.namespace_uri)
            except ValueError as exc:
                raise MappingError(f"Namespace OPC UA introuvable : {self.config.namespace_uri}") from exc
            if namespace == 0:
                raise MappingError("Namespace système 0 interdit dans le mapping FAT, y compris après résolution de l'URI")
        errors = []
        seen = set()
        for tag in self.project.tags:
            try:
                if not tag.node_id:
                    raise MappingError("NodeId absent")
                nodeid = ua.NodeId.from_string(tag.node_id)
                if nodeid.NamespaceIndex == 0:
                    raise MappingError("Namespace système 0 interdit dans le mapping FAT")
                if namespace is not None:
                    # asyncua 1.1.8 NodeId is a frozen dataclass.
                    nodeid = ua.NodeId(nodeid.Identifier, namespace, nodeid.NodeIdType)
                identity = nodeid.to_string()
                if identity in seen:
                    raise MappingError("NodeId dupliqué après résolution du namespace")
                seen.add(identity)
                node = self.client.get_node(nodeid)
                actual_type = await node.read_data_type_as_variant_type()
                expected_type = VARIANT_TYPES[tag.data_type]
                if actual_type != expected_type:
                    raise MappingError(f"Type serveur {actual_type.name}, attendu {expected_type.name}")
                if await node.read_value_rank() != ua.ValueRank.Scalar:
                    raise MappingError("Variable non scalaire : tableaux et structures ne sont pas pris en charge")
                permissions = await node.get_user_access_level()
                access = await node.get_access_level()
                if tag.direction == "input":
                    if not tag.writable:
                        raise MappingError("Entrée simulée non autorisée en écriture")
                    if ua.AccessLevel.CurrentWrite not in permissions or ua.AccessLevel.CurrentWrite not in access:
                        raise MappingError("Variable non accessible en écriture pour cet utilisateur")
                if tag.direction == "output" and (ua.AccessLevel.CurrentRead not in permissions or ua.AccessLevel.CurrentRead not in access):
                    raise MappingError("Commande PLC non accessible en lecture")
                self.nodes[tag.id] = node
            except (ValueError, ua.UaError) as exc:
                errors.append(f"{tag.name}: {exc}")
        if errors:
            raise MappingError("Mapping OPC UA invalide avant écriture :\n" + "\n".join(errors))

    async def disconnect(self) -> None:
        self.connected = False
        self.nodes.clear()
        if self.client is not None:
            client, self.client = self.client, None
            try:
                async with asyncio.timeout(self.config.timeout_s):
                    await client.disconnect()
            except (OSError, ConnectionError, TimeoutError, ua.UaError):
                # A failed disconnect cannot re-enable a write or hide the original transport fault.
                pass
            finally:
                # Also covers cancellation and unexpected client cleanup errors.
                # Closing the local transport is idempotent in asyncua.
                client.disconnect_socket()

    async def read(self, values: dict, dt: float) -> dict:
        if not self.connected or self.client is None:
            raise ConnectionError("OPC UA déconnecté.")
        try:
            async with asyncio.timeout(self.config.timeout_s):
                await self.client.check_connection()
                # Server state is a transport diagnostic, not evidence that the PLC CPU is in RUN.
                server_state = await self.client.nodes.server_state.read_value()
                if server_state != ua.ServerState.Running:
                    raise ConnectionError(f"Serveur OPC UA hors service : état {server_state}")
                results = (await self.client.read_attributes([self.nodes[key] for key in self.output_ids])
                           if self.output_ids else [])
            if len(results) != len(self.output_ids):
                raise ConnectionError("Réponse OPC UA incomplète.")
            commands = {}
            for tag_id, result in zip(self.output_ids, results, strict=True):
                if not result.StatusCode.is_good():
                    raise ConnectionError(f"Qualité OPC UA invalide sur {tag_id}: {result.StatusCode.name}")
                if result.Value is None or result.Value.VariantType != VARIANT_TYPES[self.tags[tag_id].data_type]:
                    raise MappingError(f"Type de valeur inattendu pour {tag_id}.")
                commands[tag_id] = validate_tag_value(self.tags[tag_id], result.Value.Value)
            return commands
        except BaseException:
            # A failed/partial read must never be followed by writes in this session.
            self.connected = False
            raise

    async def write(self, values: dict) -> None:
        if not self.connected or self.client is None:
            raise ConnectionError("Écriture interdite : session déconnectée.")
        try:
            if set(values) != set(self.input_ids):
                raise MappingError("Le lot d'écriture doit correspondre exactement aux entrées simulées autorisées.")
            nodes, data = [], []
            for tag_id in self.input_ids:
                tag = self.tags[tag_id]
                # Intentional out-of-range faults may exceed engineering limits, never the PLC datatype.
                value = validate_tag_value(tag, values[tag_id], allow_out_of_range=True)
                nodes.append(self.nodes[tag_id])
                data.append(ua.DataValue(ua.Variant(value, VARIANT_TYPES[tag.data_type])))
            if not nodes:
                return
            async with asyncio.timeout(self.config.timeout_s):
                await self.client.check_connection()
                results = await self.client.write_values(nodes, data, raise_on_partial_error=False)
            self.write_count += sum(result.is_good() for result in results[:len(nodes)])
            if len(results) != len(nodes) or any(not result.is_good() for result in results):
                statuses = {key: results[index].name if index < len(results) else "NoStatusReturned"
                            for index, key in enumerate(self.input_ids)}
                if len(results) > len(nodes):
                    statuses["unexpected_status_count"] = len(results) - len(nodes)
                raise PartialWriteError(statuses)
        except BaseException:
            self.connected = False
            raise
