"""Bounded OPC UA metadata browsing through the same local identity boundary."""

from __future__ import annotations

import asyncio
import re

from asyncua import ua
from asyncua.client.ua_client import UaClient, UASocketProtocol
from asyncua.common.connection import TransportLimits
from asyncua.common.shortcuts import Shortcuts

from .adapters.opcua import IdentityClient, MappingError, OpcUaAdapter


PAGE_SIZE = 100
MAX_OFFSET = 1900
MAX_WIRE_CHUNK = 65535
MAX_WIRE_CHUNKS = 64
MAX_WIRE_MESSAGE = MAX_WIRE_CHUNK * MAX_WIRE_CHUNKS
MAX_PENDING_BYTES = 1024 * 1024
BUILTIN_TYPES = {ua.ObjectIds.Boolean: "BOOL", ua.ObjectIds.Int16: "INT",
                 ua.ObjectIds.Int32: "DINT", ua.ObjectIds.Float: "REAL"}


class MetadataLimits(TransportLimits):
    """The peer ACK may reduce limits but cannot remove these local ceilings."""

    def __init__(self):
        super().__init__(MAX_WIRE_CHUNK, MAX_WIRE_CHUNK, MAX_WIRE_CHUNKS, MAX_WIRE_MESSAGE)

    def update_client_limits(self, message):
        super().update_client_limits(message)
        for name, ceiling in (("max_recv_buffer", MAX_WIRE_CHUNK), ("max_send_buffer", MAX_WIRE_CHUNK),
                              ("max_chunk_count", MAX_WIRE_CHUNKS), ("max_message_size", MAX_WIRE_MESSAGE)):
            value = getattr(self, name)
            setattr(self, name, min(value, ceiling) if value > 0 else ceiling)


class MetadataProtocol(UASocketProtocol):
    def __init__(self, timeout, security_policy):
        super().__init__(timeout, security_policy, limits=MetadataLimits())
        self._metadata_aborted = False

    def data_received(self, data: bytes) -> None:
        # asyncua 1.1.8 buffers an incomplete packet before inspecting chunk limits.
        # Bound that buffer too, without replacing its parser or encryption code.
        if self._metadata_aborted:
            return
        if len(data) + len(self.receive_buffer or b"") > MAX_PENDING_BYTES:
            self._metadata_aborted = True
            self.receive_buffer = None
            for future in self._callbackmap.values():
                if not future.done():
                    future.set_exception(MappingError("Réponse OPC UA trop volumineuse ; exploration interrompue."))
            self.disconnect_socket()
            return
        super().data_received(data)


class MetadataUaClient(UaClient):
    def _make_protocol(self):
        self.protocol = MetadataProtocol(self._timeout, self.security_policy)
        self.protocol.pre_request_hook = self._pre_request_hook
        return self.protocol


class MetadataIdentityClient(IdentityClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uaclient = MetadataUaClient(self.uaclient._timeout)
        self.uaclient.pre_request_hook = self.check_connection
        self.nodes = Shortcuts(self.uaclient)
        self.max_messagesize = MAX_WIRE_MESSAGE
        self.max_chunkcount = MAX_WIRE_CHUNKS


def parent_node_id(text: str):
    # asyncua accepts unknown prefix fields; accept only local NodeId spellings.
    if not re.fullmatch(r"(?:ns=[0-9]+;)?(?:i=[0-9]+|s=.+|g=[0-9a-fA-F-]{36}|b=[A-Za-z0-9+/]*={0,2})", text, re.DOTALL):
        raise MappingError("NodeId OPC UA local attendu ; les références externes ne sont pas parcourues.")
    try:
        node = ua.NodeId.from_string(text)
    except (ValueError, TypeError, ua.UaError) as exc:
        raise MappingError("NodeId OPC UA de dossier invalide.") from exc
    if not 0 <= node.NamespaceIndex <= 65535:
        raise MappingError("Index de namespace OPC UA hors de la plage UInt16.")
    if type(node.Identifier) is int and not 0 <= node.Identifier <= 4_294_967_295:
        raise MappingError("Identifiant numérique OPC UA hors de la plage UInt32.")
    if getattr(node, "ServerIndex", 0) or getattr(node, "NamespaceUri", None):
        raise MappingError("Les références OPC UA externes ne sont pas parcourues.")
    if node.NamespaceIndex == 0 and node != ua.NodeId(ua.ObjectIds.ObjectsFolder):
        raise MappingError("Namespace système non parcourable hors du dossier Objets.")
    return node


class MetadataBrowser(OpcUaAdapter):
    """Mapping may be incomplete while discovering it; transport identity may not."""

    namespace_index = None

    def _create_client(self) -> IdentityClient:
        return MetadataIdentityClient(self.config.endpoint, timeout=self.config.timeout_s, identity_check=self._check_identity)

    async def _validate_nodes(self) -> None:
        assert self.client is not None
        if self.config.namespace_uri:
            try:
                self.namespace_index = await self.client.get_namespace_index(self.config.namespace_uri)
            except ValueError as exc:
                raise MappingError(f"Namespace OPC UA introuvable : {self.config.namespace_uri}") from exc
            if self.namespace_index == 0:
                raise MappingError("Namespace système 0 interdit dans le mapping FAT.")

    async def write(self, values: dict) -> None:
        raise MappingError("L'explorateur OPC UA est en lecture seule.")

    async def page(self, node_id: str, offset: int) -> dict:
        assert self.client is not None and self.connected
        parent = parent_node_id(node_id)
        description = ua.BrowseDescription()
        description.NodeId = parent
        description.BrowseDirection = ua.BrowseDirection.Forward
        description.ReferenceTypeId = ua.NodeId(ua.ObjectIds.HierarchicalReferences)
        description.IncludeSubtypes = True
        description.NodeClassMask = ua.NodeClass.Object | ua.NodeClass.Variable
        description.ResultMask = ua.BrowseResultMask.All
        parameters = ua.BrowseParameters()
        parameters.RequestedMaxReferencesPerNode = PAGE_SIZE
        parameters.NodesToBrowse = [description]
        results = await self.client.uaclient.browse(parameters)
        references = []
        continuation = None
        try:
            for _ in range(MAX_OFFSET + PAGE_SIZE + 1):
                if len(results) != 1:
                    raise MappingError("Réponse Browse OPC UA incomplète.")
                result = results[0]
                result.StatusCode.check()
                continuation = result.ContinuationPoint
                if len(result.References) > MAX_OFFSET + PAGE_SIZE:
                    raise MappingError("Le serveur renvoie trop de références pour une page de découverte.")
                if not result.References and continuation:
                    raise MappingError("Le serveur renvoie une page vide avec une suite ; exploration interrompue.")
                references.extend(result.References[:offset + PAGE_SIZE + 1 - len(references)])
                if len(references) > offset + PAGE_SIZE or not continuation:
                    break
                follow = ua.BrowseNextParameters()
                follow.ReleaseContinuationPoints = False
                follow.ContinuationPoints = [continuation]
                results = await self.client.uaclient.browse_next(follow)
            more = len(references) > offset + PAGE_SIZE or bool(continuation)
        finally:
            if continuation:
                release = ua.BrowseNextParameters()
                release.ReleaseContinuationPoints = True
                release.ContinuationPoints = [continuation]
                await self.client.uaclient.browse_next(release)

        limiter = asyncio.Semaphore(10)

        async def describe(reference):
            async with limiter:
                return await self.describe(reference)

        nodes = await asyncio.gather(*(describe(reference) for reference in references[offset:offset + PAGE_SIZE]))
        return {"node_id": parent.to_string(), "nodes": nodes, "offset": offset, "limit": PAGE_SIZE,
                "more": more, "namespace_index": self.namespace_index}

    async def describe(self, reference) -> dict:
        nodeid = reference.NodeId
        identifier = ua.NodeId(nodeid.Identifier, nodeid.NamespaceIndex, nodeid.NodeIdType).to_string()
        result = {"node_id": identifier, "name": (reference.DisplayName.Text or reference.BrowseName.Name or identifier)[:300],
                  "kind": "object" if reference.NodeClass == ua.NodeClass.Object else "variable",
                  "data_type": None, "readable": False, "writable": False, "selectable": False, "reason": ""}
        if len(identifier) > 1000:
            result["reason"] = "NodeId trop long pour le format de projet (1 000 caractères maximum)."
            return result
        if getattr(nodeid, "ServerIndex", 0) or getattr(nodeid, "NamespaceUri", None):
            result["reason"] = "Référence externe non prise en charge."
            return result
        if nodeid.NamespaceIndex == 0:
            result["reason"] = "Namespace système, association interdite."
            return result
        if result["kind"] == "object":
            return result
        try:
            node = self.client.get_node(identifier)
            attrs = await node.read_attributes([ua.AttributeIds.DataType, ua.AttributeIds.ValueRank,
                                               ua.AttributeIds.AccessLevel, ua.AttributeIds.UserAccessLevel])
            if len(attrs) != 4:
                raise MappingError("Métadonnées incomplètes.")
            for value in attrs:
                value.StatusCode.check()
                if value.Value is None:
                    raise MappingError("Métadonnée absente.")
            datatype, rank, access, user_access = [value.Value.Value for value in attrs]
            result["data_type"] = BUILTIN_TYPES.get(datatype.Identifier) if datatype.NamespaceIndex == 0 else None
            result["readable"] = bool(access & user_access & (1 << ua.AccessLevel.CurrentRead))
            result["writable"] = bool(access & user_access & (1 << ua.AccessLevel.CurrentWrite))
            if self.namespace_index is not None and nodeid.NamespaceIndex != self.namespace_index:
                result["reason"] = "Variable hors du namespace configuré."
            elif rank != ua.ValueRank.Scalar:
                result["reason"] = "Tableaux et structures non pris en charge."
            elif result["data_type"] is None:
                result["reason"] = "Type serveur non pris en charge par le banc."
            else:
                result["selectable"] = True
        except (ValueError, TypeError, AttributeError, ua.UaError) as exc:
            result["reason"] = f"Métadonnées indisponibles : {exc}"[:500]
        return result


async def browse_metadata(project, policy, confirmation: str, node_id: str = "i=85", offset: int = 0) -> dict:
    if project.plc.mode != "opcua":
        raise MappingError("Choisissez le mode OPC UA pour parcourir une cible.")
    if type(offset) is not int or not 0 <= offset <= MAX_OFFSET or offset % PAGE_SIZE:
        raise MappingError("Page OPC UA invalide.")
    parent_node_id(node_id)
    # The browser is finite and does not inherit a long-running test timeout.
    bounded = project.model_copy(deep=True)
    bounded.plc.timeout_s = min(project.plc.timeout_s, 3.0)
    adapter = MetadataBrowser(bounded, policy, confirmation)
    try:
        async with asyncio.timeout(20):
            await adapter.connect()
            return await adapter.page(node_id, offset)
    except ua.UaError as exc:
        raise MappingError(f"Exploration OPC UA refusée : {exc}. Aucune écriture effectuée.") from exc
    finally:
        await adapter.disconnect()
