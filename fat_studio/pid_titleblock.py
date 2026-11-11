"""Declared drawing-office metadata; no signatures or engineering approvals."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DrawingModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True, allow_inf_nan=False)

    @field_validator("*", mode="before")
    @classmethod
    def printable_text(cls, value, info):
        if isinstance(value, str):
            allowed = "\n\t" if info.field_name == "notes" else ""
            if any((ord(character) < 32 or ord(character) == 127) and character not in allowed for character in value):
                raise ValueError("Les champs du cartouche ne peuvent pas contenir de caractères de contrôle.")
        return value


def _valid_date(value: str) -> str:
    if value:
        if len(value) != 10:
            raise ValueError("Date attendue au format AAAA-MM-JJ, ou champ vide.")
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Date du cartouche invalide ; utiliser AAAA-MM-JJ.") from exc
        if parsed.isoformat() != value:
            raise ValueError("Date attendue au format AAAA-MM-JJ.")
    return value


class DrawingRevision(DrawingModel):
    revision: str = Field(min_length=1, max_length=16)
    date: str = Field(default="", max_length=10)
    description: str = Field(min_length=1, max_length=140)
    drawn_by: str = Field(default="", max_length=64)
    checked_by: str = Field(default="", max_length=64)
    approved_by: str = Field(default="", max_length=64)

    _date = field_validator("date")(_valid_date)


class PidDrawingSettings(DrawingModel):
    layout_style: Literal["compact", "full"] = "compact"
    color_mode: Literal["service", "monochrome"] = "service"
    paper_size: Literal["A4", "A3", "A2", "A1", "A0"] = "A3"
    orientation: Literal["landscape", "portrait"] = "landscape"
    company: str = Field(default="", max_length=100)
    client: str = Field(default="", max_length=100)
    project_reference: str = Field(default="", max_length=64)
    site: str = Field(default="", max_length=100)
    unit: str = Field(default="", max_length=80)
    drawing_title: str = Field(default="", max_length=160)
    document_number: str = Field(default="", max_length=64)
    revision: str = Field(default="00", max_length=16)
    issue_date: str = Field(default="", max_length=10)
    drawn_by: str = Field(default="", max_length=64)
    checked_by: str = Field(default="", max_length=64)
    approved_by: str = Field(default="", max_length=64)
    status: Literal["draft", "for_review", "for_information", "for_construction", "as_built"] = "draft"
    sheet_number: int = Field(default=1, ge=1, le=999, strict=True)
    sheet_total: int = Field(default=1, ge=1, le=999, strict=True)
    notes: str = Field(default="", max_length=1200)
    revisions: list[DrawingRevision] = Field(default_factory=list, max_length=5)
    show_legend: bool = True

    _date = field_validator("issue_date")(_valid_date)

    @model_validator(mode="before")
    @classmethod
    def coherent_folio(cls, values):
        # Assignment validation must reject the candidate before Pydantic writes
        # it to an existing model; an after-validator leaves a failed edit behind.
        number = values.get("sheet_number", 1) if isinstance(values, dict) else 1
        total = values.get("sheet_total", 1) if isinstance(values, dict) else 1
        if type(number) is int and type(total) is int and number > total:
            raise ValueError("Le numéro de folio ne peut pas dépasser le total déclaré du dossier.")
        return values
