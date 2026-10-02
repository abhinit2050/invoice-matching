"""Deterministic two-way matching engine (docs/specs.md section 6).

The LLM only extracts data (core/llm_extract.py). This module decides
PASS / DISCREPANCY / REVIEW using plain comparisons over Decimal values —
no LLM calls here, and nothing here ever invents a missing value.
"""

from __future__ import annotations

import re
from decimal import Decimal

from core.config import (
    DISCOUNT_TOLERANCE,
    QUANTITY_TOLERANCE,
    TAX_TOLERANCE,
    TOTAL_AMOUNT_TOLERANCE,
    UNIT_PRICE_TOLERANCE,
)
from core.models import CheckResult, CheckStatus, Invoice, LineItem, MatchReport, MatchStatus, PurchaseOrder


def _normalize(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _item_code_key(code: str | None) -> str | None:
    code = (code or "").strip().lower()
    return code or None


def _within_tolerance(a: Decimal | None, b: Decimal | None, tolerance: Decimal) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tolerance


# ---------------------------------------------------------------------------
# 6.1 Vendor matching
# ---------------------------------------------------------------------------

def check_vendor(po: PurchaseOrder, invoice: Invoice) -> CheckResult:
    po_name, inv_name = _normalize(po.vendor_name), _normalize(invoice.vendor_name)
    if not po_name or not inv_name:
        return CheckResult(
            check_name="vendor", status=CheckStatus.REVIEW,
            explanation="Vendor name is missing on the PO or the invoice.",
        )
    if po_name == inv_name:
        return CheckResult(check_name="vendor", status=CheckStatus.PASS_, explanation="Vendor names match.")
    return CheckResult(
        check_name="vendor", status=CheckStatus.REVIEW,
        explanation=(
            f"Vendor names differ: PO '{po.vendor_name}' vs invoice '{invoice.vendor_name}'. "
            "Could not confirm whether these refer to the same vendor."
        ),
    )


# ---------------------------------------------------------------------------
# 6.2 PO reference validation
# ---------------------------------------------------------------------------

def check_po_reference(po: PurchaseOrder, invoice: Invoice) -> CheckResult:
    po_number, inv_ref = _normalize(po.po_number), _normalize(invoice.po_number)
    if not inv_ref:
        return CheckResult(
            check_name="po_reference", status=CheckStatus.REVIEW,
            explanation="Invoice does not reference a PO number.",
        )
    if not po_number:
        return CheckResult(
            check_name="po_reference", status=CheckStatus.REVIEW,
            explanation="PO number is missing on the purchase order itself.",
        )
    if po_number == inv_ref:
        return CheckResult(
            check_name="po_reference", status=CheckStatus.PASS_,
            explanation="Invoice references the correct PO number.",
        )
    return CheckResult(
        check_name="po_reference", status=CheckStatus.DISCREPANCY,
        explanation=f"Invoice references PO '{invoice.po_number}', expected '{po.po_number}'.",
    )


# ---------------------------------------------------------------------------
# 6.3 Line-item pairing
# ---------------------------------------------------------------------------

def pair_line_items(
    po_items: list[LineItem], invoice_items: list[LineItem]
) -> tuple[list[tuple[LineItem, LineItem]], list[tuple[LineItem, LineItem]], list[LineItem], list[LineItem]]:
    """Pair PO and invoice line items per spec section 6.3.

    Preference order: item code/SKU, then normalized description. A PO/invoice
    item left over on both sides that shares quantity and unit price is treated
    as an ambiguous match (same item, unconfirmable description) rather than a
    confident new/missing item.

    Returns (confident_pairs, ambiguous_pairs, unmatched_po, unmatched_invoice).
    """
    remaining_invoice = list(invoice_items)

    def _take(predicate):
        return next((inv for inv in remaining_invoice if predicate(inv)), None)

    confident: list[tuple[LineItem, LineItem]] = []

    remaining_po = []
    for po_item in po_items:
        code = _item_code_key(po_item.item_code)
        match = _take(lambda inv, code=code: code is not None and _item_code_key(inv.item_code) == code)
        if match:
            confident.append((po_item, match))
            remaining_invoice.remove(match)
        else:
            remaining_po.append(po_item)

    still_remaining_po = []
    for po_item in remaining_po:
        desc = _normalize(po_item.description)
        match = _take(lambda inv, desc=desc: desc != "" and _normalize(inv.description) == desc)
        if match:
            confident.append((po_item, match))
            remaining_invoice.remove(match)
        else:
            still_remaining_po.append(po_item)

    ambiguous: list[tuple[LineItem, LineItem]] = []
    unmatched_po = []
    for po_item in still_remaining_po:
        match = _take(
            lambda inv, po_item=po_item: (
                inv.quantity is not None and inv.quantity == po_item.quantity
                and inv.unit_price is not None and inv.unit_price == po_item.unit_price
            )
        )
        if match:
            ambiguous.append((po_item, match))
            remaining_invoice.remove(match)
        else:
            unmatched_po.append(po_item)

    return confident, ambiguous, unmatched_po, remaining_invoice


def _item_label(item: LineItem) -> str:
    return item.item_code or item.description or "line item"


# ---------------------------------------------------------------------------
# 6.4-6.7 Per-line-item field checks (quantity, unit price, discount, tax)
# ---------------------------------------------------------------------------

def check_line_item_fields(po_item: LineItem, invoice_item: LineItem, label: str) -> list[CheckResult]:
    results: list[CheckResult] = []

    # 6.4 Quantity
    if po_item.quantity is None or invoice_item.quantity is None:
        results.append(CheckResult(
            check_name=f"quantity[{label}]", status=CheckStatus.REVIEW,
            explanation=f"Quantity missing for '{label}'.",
        ))
    elif _within_tolerance(po_item.quantity, invoice_item.quantity, QUANTITY_TOLERANCE):
        results.append(CheckResult(
            check_name=f"quantity[{label}]", status=CheckStatus.PASS_,
            explanation=f"Quantity matches for '{label}'.",
        ))
    else:
        results.append(CheckResult(
            check_name=f"quantity[{label}]", status=CheckStatus.DISCREPANCY,
            explanation=f"Quantity for '{label}': PO {po_item.quantity} vs invoice {invoice_item.quantity}.",
        ))

    # 6.5 Unit price
    if po_item.unit_price is None or invoice_item.unit_price is None:
        results.append(CheckResult(
            check_name=f"unit_price[{label}]", status=CheckStatus.REVIEW,
            explanation=f"Unit price missing for '{label}'.",
        ))
    elif _within_tolerance(po_item.unit_price, invoice_item.unit_price, UNIT_PRICE_TOLERANCE):
        results.append(CheckResult(
            check_name=f"unit_price[{label}]", status=CheckStatus.PASS_,
            explanation=f"Unit price matches for '{label}'.",
        ))
    else:
        results.append(CheckResult(
            check_name=f"unit_price[{label}]", status=CheckStatus.DISCREPANCY,
            explanation=f"Unit price for '{label}': PO {po_item.unit_price} vs invoice {invoice_item.unit_price}.",
        ))

    # 6.6 Discount — only compared when both documents actually provide a value
    if po_item.discount is not None and invoice_item.discount is not None:
        if _within_tolerance(po_item.discount, invoice_item.discount, DISCOUNT_TOLERANCE):
            results.append(CheckResult(
                check_name=f"discount[{label}]", status=CheckStatus.PASS_,
                explanation=f"Discount matches for '{label}'.",
            ))
        else:
            results.append(CheckResult(
                check_name=f"discount[{label}]", status=CheckStatus.DISCREPANCY,
                explanation=f"Discount for '{label}': PO {po_item.discount} vs invoice {invoice_item.discount}.",
            ))

    # 6.7 Tax (rate and/or amount; compared only where both sides have data)
    tax_mismatches = []
    if po_item.tax_rate is not None and invoice_item.tax_rate is not None:
        if not _within_tolerance(po_item.tax_rate, invoice_item.tax_rate, TAX_TOLERANCE):
            tax_mismatches.append(f"rate PO {po_item.tax_rate}% vs invoice {invoice_item.tax_rate}%")
    if po_item.tax_amount is not None and invoice_item.tax_amount is not None:
        if not _within_tolerance(po_item.tax_amount, invoice_item.tax_amount, TAX_TOLERANCE):
            tax_mismatches.append(f"amount PO {po_item.tax_amount} vs invoice {invoice_item.tax_amount}")
    if po_item.tax_rate is not None or po_item.tax_amount is not None or invoice_item.tax_rate is not None or invoice_item.tax_amount is not None:
        if tax_mismatches:
            results.append(CheckResult(
                check_name=f"tax[{label}]", status=CheckStatus.DISCREPANCY,
                explanation=f"Tax mismatch for '{label}': " + "; ".join(tax_mismatches),
            ))
        else:
            results.append(CheckResult(
                check_name=f"tax[{label}]", status=CheckStatus.PASS_,
                explanation=f"Tax matches for '{label}' (or not comparable on one side).",
            ))

    return results


def check_line_items(po: PurchaseOrder, invoice: Invoice) -> list[CheckResult]:
    confident, ambiguous, unmatched_po, unmatched_invoice = pair_line_items(po.line_items, invoice.line_items)
    results: list[CheckResult] = []

    for po_item, inv_item in confident:
        label = _item_label(po_item)
        results.append(CheckResult(
            check_name=f"line_item_match[{label}]", status=CheckStatus.PASS_,
            explanation=f"Matched invoice line '{inv_item.description}' to PO line '{po_item.description}'.",
        ))
        results.extend(check_line_item_fields(po_item, inv_item, label))

    for po_item, inv_item in ambiguous:
        label = _item_label(po_item)
        results.append(CheckResult(
            check_name=f"line_item_match[{label}]", status=CheckStatus.REVIEW,
            explanation=(
                f"PO line '{po_item.description}' and invoice line '{inv_item.description}' share the same "
                "quantity and unit price but their descriptions/item codes don't confirm they're the same "
                "item."
            ),
        ))

    for po_item in unmatched_po:
        label = _item_label(po_item)
        results.append(CheckResult(
            check_name=f"line_item_match[{label}]", status=CheckStatus.DISCREPANCY,
            explanation=f"PO line '{po_item.description}' has no corresponding line on the invoice.",
        ))

    for inv_item in unmatched_invoice:
        label = _item_label(inv_item)
        results.append(CheckResult(
            check_name=f"line_item_match[{label}]", status=CheckStatus.DISCREPANCY,
            explanation=f"Invoice line '{inv_item.description}' does not correspond to any PO line item (unexpected line item).",
        ))

    return results


# ---------------------------------------------------------------------------
# 6.8 Total amount matching
# ---------------------------------------------------------------------------

def check_total_amount(po: PurchaseOrder, invoice: Invoice) -> CheckResult:
    if invoice.total_amount is None:
        return CheckResult(
            check_name="total_amount", status=CheckStatus.REVIEW,
            explanation="Invoice total amount is missing.",
        )

    if not po.line_items:
        return CheckResult(
            check_name="total_amount", status=CheckStatus.REVIEW,
            explanation="PO has no line items to calculate an expected total from.",
        )

    expected = Decimal("0")
    for item in po.line_items:
        if item.quantity is None or item.unit_price is None:
            return CheckResult(
                check_name="total_amount", status=CheckStatus.REVIEW,
                explanation="Not enough PO data (missing quantity/unit price) to calculate an expected total.",
            )
        line = item.quantity * item.unit_price
        if item.discount is not None:
            line -= item.discount
        if item.tax_amount is not None:
            line += item.tax_amount
        elif item.tax_rate is not None:
            line += line * item.tax_rate / 100
        expected += line

    if invoice.additional_charges is not None:
        expected += invoice.additional_charges

    if _within_tolerance(expected, invoice.total_amount, TOTAL_AMOUNT_TOLERANCE):
        return CheckResult(
            check_name="total_amount", status=CheckStatus.PASS_,
            explanation=f"Invoice total {invoice.total_amount} matches the expected {expected}.",
        )
    return CheckResult(
        check_name="total_amount", status=CheckStatus.DISCREPANCY,
        explanation=(
            f"Invoice total {invoice.total_amount} does not match the expected {expected} "
            "calculated from the PO line items and invoice additional charges."
        ),
    )


# ---------------------------------------------------------------------------
# Orchestration
#
# Split into composable pieces (rather than one function) so the LangGraph
# workflow (graph/workflow.py) can run "matching", "discrepancy identification"
# and "report generation" as separate nodes per docs/specs.md section 8.2,
# without reimplementing this logic a second time.
# ---------------------------------------------------------------------------

def run_checks(po: PurchaseOrder, invoice: Invoice) -> list[CheckResult]:
    return [
        check_vendor(po, invoice),
        check_po_reference(po, invoice),
        *check_line_items(po, invoice),
        check_total_amount(po, invoice),
    ]


def split_checks(checks: list[CheckResult]) -> tuple[list[str], list[str]]:
    """Returns (discrepancies, review_reasons) explanation strings."""
    discrepancies = [c.explanation for c in checks if c.status == CheckStatus.DISCREPANCY and c.explanation]
    review_reasons = [c.explanation for c in checks if c.status == CheckStatus.REVIEW and c.explanation]
    return discrepancies, review_reasons


def derive_overall_status(discrepancies: list[str], review_reasons: list[str]) -> MatchStatus:
    """Overall status is PASS or REVIEW only (docs/specs.md section 7). Any
    confirmed discrepancy or any inconclusive comparison must never resolve to
    PASS; when both exist, the REVIEW report surfaces both."""
    return MatchStatus.REVIEW if (discrepancies or review_reasons) else MatchStatus.PASS_


def build_match_report(po: PurchaseOrder, invoice: Invoice, checks: list[CheckResult]) -> MatchReport:
    discrepancies, review_reasons = split_checks(checks)
    return MatchReport(
        status=derive_overall_status(discrepancies, review_reasons),
        invoice_number=invoice.invoice_number,
        po_number=po.po_number,
        vendor_name=invoice.vendor_name or po.vendor_name,
        checks=checks,
        discrepancies=discrepancies,
        review_reasons=review_reasons,
    )


def match_invoice_to_po(po: PurchaseOrder, invoice: Invoice) -> MatchReport:
    """Convenience single-call entry point for use outside the LangGraph
    workflow (tests, ad-hoc scripts). The graph itself calls run_checks(),
    split_checks() and derive_overall_status() as separate nodes."""
    return build_match_report(po, invoice, run_checks(po, invoice))
