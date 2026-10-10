"""Trusted drawing-evidence extension boundary; PDF recognition is reserved."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, TypedDict

from .contracts import require
from .evidence import collect_dxf, collect_relations


class _OptionalEvidence(TypedDict, total=False):
    nominal_equations: list[dict]
    verified_annotation_ids: list[str]


class DrawingEvidence(_OptionalEvidence):
    equations: list[dict]
    structures: list[dict]
    rejected: list[dict]
    unsupported: list[dict]
    views: list[dict]
    drawing_verified: bool
    view_count: int


class EvidenceAdapter(Protocol):
    """Only evaluator-owned code may produce trusted drawing evidence."""

    def __call__(self, gt: dict, prediction: dict, drawing: Path | None,
                 rules: dict) -> DrawingEvidence: ...


class AdapterUnavailable(Exception):
    """Explicitly unavailable adapter, distinct from a malformed submission."""


def collect_pdf(gt, prediction, drawing, rules) -> DrawingEvidence:
    """Extension point only: no parsing, OCR, or JSON evidence substitution."""
    require(drawing is not None, "pdf requires --drawing")
    path = Path(drawing)
    require(path.suffix.lower() == ".pdf", "pdf requires a .pdf drawing")
    require(path.is_file(), "PDF drawing file does not exist")
    raise AdapterUnavailable("PDF evidence recognition is reserved but not implemented")


def _collect_relations(gt, prediction, drawing, rules):
    return collect_relations(gt, prediction)


ADAPTERS: dict[str, EvidenceAdapter] = {
    "relations-only": _collect_relations,
    "controlled-dxf": collect_dxf,
    "pdf": collect_pdf,
}


def get_adapter(mode: str) -> EvidenceAdapter:
    if mode not in ADAPTERS:
        raise ValueError(f"Unsupported evidence adapter: {mode}")
    return ADAPTERS[mode]
