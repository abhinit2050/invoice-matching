from __future__ import annotations

from typing import TypedDict

from core.models import CheckResult, Invoice, MatchReport, PurchaseOrder


class GraphState(TypedDict, total=False):
    """docs/specs.md section 8.2. Each node returns only the keys it changes.

    po_*_error / invoice_*_error are kept as separate keys (not one shared
    "errors" list) so the parallel PO/invoice extraction branches never write
    the same state key in the same step.
    """

    po_path: str
    invoice_path: str

    po_text: str | None
    invoice_text: str | None
    po_text_error: str | None
    invoice_text_error: str | None

    po_data: PurchaseOrder | None
    invoice_data: Invoice | None
    po_data_error: str | None
    invoice_data_error: str | None

    validation_errors: list[str]

    checks: list[CheckResult]
    discrepancies: list[str]
    review_reasons: list[str]

    report: MatchReport | None
