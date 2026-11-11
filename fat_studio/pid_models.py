"""Local, versioned P&ID interchange independent of PLC authorizations."""

from __future__ import annotations

import base64
import struct
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .pid_titleblock import PidDrawingSettings
from .pid_conventions import PidService


class PidModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class PidPosition(PidModel):
    x: float = Field(default=0, ge=-100000, le=100000)
    y: float = Field(default=0, ge=-100000, le=100000)


class PidEquipment(PidModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(default="unknown", max_length=80)
    source_tag: str = Field(default="", max_length=200)
    position: PidPosition = Field(default_factory=PidPosition)
    page: int = Field(default=1, ge=1, le=10000)
    confidence: float = Field(default=0.5, ge=0, le=1)
    provenance: str = Field(default="", max_length=1000)
    review_required: bool = True
    source_kind: str = Field(default="", max_length=80)
    rotation: Literal[0, 90, 180, 270] = 0
    documentary: bool = False

    @field_validator("rotation", mode="before")
    @classmethod
    def orthogonal_rotation(cls, value):
        if type(value) is not int or value not in (0, 90, 180, 270):
            raise ValueError("Rotation entière attendue : 0, 90, 180 ou 270 degrés.")
        return value


class PidConnection(PidModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")
    source: str = Field(max_length=80)
    target: str = Field(max_length=80)
    label: str = Field(default="", max_length=200)
    service: PidService = "unspecified"
    directed: bool = False
    inferred: bool = True
    confidence: float = Field(default=0.5, ge=0, le=1)
    source_port: str = Field(default="", max_length=80)
    target_port: str = Field(default="", max_length=80)


class PidPage(PidModel):
    number: int = Field(ge=1, le=10000)
    width: float = Field(default=1000, gt=0, le=100000)
    height: float = Field(default=700, gt=0, le=100000)
    image_data_url: str = Field(default="", max_length=4_000_000)
    text: str = Field(default="", max_length=200000)

    @field_validator("image_data_url")
    @classmethod
    def png_preview(cls, value: str) -> str:
        if not value:
            return value
        prefix = "data:image/png;base64,"
        if not value.startswith(prefix):
            raise ValueError("L'aperçu doit être une image PNG locale.")
        try:
            image = base64.b64decode(value[len(prefix):], validate=True)
        except ValueError as exc:
            raise ValueError("Aperçu PNG mal encodé.") from exc
        if len(image) < 33 or image[:8] != b"\x89PNG\r\n\x1a\n" or image[12:16] != b"IHDR":
            raise ValueError("Aperçu PNG invalide.")
        width, height = struct.unpack(">II", image[16:24])
        if not width or not height or width * height > 16_000_000:
            raise ValueError("Dimensions de l'aperçu trop grandes.")
        return value


class PidDocument(PidModel):
    format: Literal["fat-studio/pid"] = "fat-studio/pid"
    version: Literal["1.0"] = "1.0"
    title: str = Field(default="P&ID importé", min_length=1, max_length=200)
    source_name: str = Field(default="", max_length=240)
    source_format: str = Field(default="json", max_length=40)
    source_sha256: str = Field(default="", max_length=64)
    equipment: list[PidEquipment] = Field(default_factory=list, max_length=2000)
    connections: list[PidConnection] = Field(default_factory=list, max_length=5000)
    pages: list[PidPage] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=300)
    metadata: dict[str, str] = Field(default_factory=dict, max_length=40)
    drawing: PidDrawingSettings = Field(default_factory=PidDrawingSettings)

    @model_validator(mode="after")
    def bounded_document(self):
        identifiers = [item.id for item in self.equipment]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Identifiants P&ID dupliqués.")
        known = set(identifiers)
        links = [item.id for item in self.connections]
        if len(set(links)) != len(links):
            raise ValueError("Identifiants de liaisons P&ID dupliqués.")
        if any(link.source not in known or link.target not in known for link in self.connections):
            raise ValueError("Une liaison P&ID référence un objet absent.")
        if any(len(warning) > 2000 for warning in self.warnings):
            raise ValueError("Un avertissement P&ID est trop long.")
        if any(len(key) > 100 or len(value) > 4000 for key, value in self.metadata.items()):
            raise ValueError("Métadonnées P&ID trop longues.")
        if len(self.model_dump_json().encode("utf-8")) > 4 * 1024 * 1024:
            raise ValueError("Le document P&ID dépasse 4 Mo ; réduire les pages ou la résolution des aperçus.")
        return self
