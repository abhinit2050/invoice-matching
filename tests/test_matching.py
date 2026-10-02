"""Matching engine tests (docs/plan.md Day 2 step 2): hand-built Pydantic
objects only — no PDFs, no LLM. Covers the 14 scenarios in docs/specs.md
section 13 that apply at this layer (scenario 13, the unreadable PDF, is a
core.pdf_text concern and is covered separately)."""

from decimal import Decimal

from core.matching import match_invoice_to_po, pair_line_items
from core.models import LineItem, MatchStatus


# ---------------------------------------------------------------------------
# Scenario 1 — exact match
# ---------------------------------------------------------------------------

def test_exact_match_passes(po, invoice):
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.PASS_
    assert report.discrepancies == []
    assert report.review_reasons == []


# ---------------------------------------------------------------------------
# Scenarios 2-3 — unit price higher/lower
# ---------------------------------------------------------------------------

def test_higher_unit_price_is_a_discrepancy(po, invoice):
    invoice.line_items[0].unit_price = Decimal("550.00")
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert report.review_reasons == []
    assert any("unit price" in d.lower() for d in report.discrepancies)


def test_lower_unit_price_is_a_discrepancy(po, invoice):
    invoice.line_items[0].unit_price = Decimal("450.00")
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert any("unit price" in d.lower() for d in report.discrepancies)


# ---------------------------------------------------------------------------
# Scenarios 4-5 — quantity exceeds/below PO
# ---------------------------------------------------------------------------

def test_quantity_exceeds_po_is_a_discrepancy(po, invoice):
    invoice.line_items[0].quantity = Decimal("120")
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert any("quantity" in d.lower() for d in report.discrepancies)


def test_quantity_below_po_is_a_discrepancy(po, invoice):
    invoice.line_items[0].quantity = Decimal("80")
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert any("quantity" in d.lower() for d in report.discrepancies)


# ---------------------------------------------------------------------------
# Scenario 6 — unexpected line item (+ the symmetric "missing" case)
# ---------------------------------------------------------------------------

def test_unexpected_line_item_is_a_discrepancy(po, invoice):
    invoice.line_items.append(
        LineItem(description="Steel Rod 8mm", item_code="SR-08", quantity="20",
                  unit_price="400.00", tax_rate="18", tax_amount="1440.00", line_total="9440.00")
    )
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert any("unexpected" in d.lower() for d in report.discrepancies)


def test_missing_po_line_item_is_a_discrepancy(po, invoice):
    invoice.line_items.pop()  # invoice drops the SR-12 line entirely
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert any("no corresponding line" in d.lower() for d in report.discrepancies)


# ---------------------------------------------------------------------------
# Scenario 7 — incorrect / missing PO reference
# ---------------------------------------------------------------------------

def test_wrong_po_reference_is_a_discrepancy(po, invoice):
    invoice.po_number = "PO-9999"
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert report.discrepancies and not report.review_reasons
    assert "PO-9999" in report.discrepancies[0]


def test_missing_po_reference_needs_review(po, invoice):
    invoice.po_number = None
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert report.review_reasons and not report.discrepancies


# ---------------------------------------------------------------------------
# Scenario 8 — vendor names differ
# ---------------------------------------------------------------------------

def test_vendor_mismatch_needs_review_not_discrepancy(po, invoice):
    invoice.vendor_name = "Acme Supply Co."
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert report.review_reasons and not report.discrepancies


def test_vendor_name_case_and_whitespace_are_ignored(po, invoice):
    invoice.vendor_name = "  ACME supplies pvt ltd  "
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.PASS_


# ---------------------------------------------------------------------------
# Scenario 9 — tax discrepancy
# ---------------------------------------------------------------------------

def test_tax_discrepancy(po, invoice):
    invoice.line_items[0].tax_rate = Decimal("12")
    invoice.line_items[0].tax_amount = Decimal("6000.00")
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert any("tax" in d.lower() for d in report.discrepancies)


# ---------------------------------------------------------------------------
# Scenario 10 — discount discrepancy
# ---------------------------------------------------------------------------

def test_discount_discrepancy(po, invoice):
    invoice.line_items[0].discount = Decimal("2000.00")
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert any("discount" in d.lower() for d in report.discrepancies)


# ---------------------------------------------------------------------------
# Scenario 11 — required fields missing
# ---------------------------------------------------------------------------

def test_missing_invoice_total_needs_review(po, invoice):
    invoice.total_amount = None
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert any("total amount" in r.lower() for r in report.review_reasons)
    assert report.discrepancies == []


# ---------------------------------------------------------------------------
# Scenario 12 — line item cannot be matched confidently
# ---------------------------------------------------------------------------

def test_ambiguous_line_item_needs_review(po, invoice):
    invoice.line_items[0] = LineItem(
        description="10mm rebar (misc grade)", item_code=None,
        quantity="100", unit_price="500.00", tax_rate="18",
        tax_amount="9000.00", line_total="59000.00",
    )
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert report.review_reasons and not report.discrepancies


# ---------------------------------------------------------------------------
# Scenario 14 — total amount mismatch
# ---------------------------------------------------------------------------

def test_total_amount_mismatch_is_a_discrepancy(po, invoice):
    invoice.total_amount = Decimal("97850.00")  # correct total is 97350.00
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert any("total" in d.lower() for d in report.discrepancies)


def test_total_amount_cannot_be_calculated_needs_review(po, invoice):
    po.line_items[0].unit_price = None  # PO itself lacks the data needed to calculate a total
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert any("expected total" in r.lower() for r in report.review_reasons)


# ---------------------------------------------------------------------------
# A discrepancy and a review reason can coexist in a single REVIEW report
# ---------------------------------------------------------------------------

def test_discrepancy_and_review_reason_can_coexist(po, invoice):
    invoice.line_items.append(
        LineItem(description="Steel Rod 8mm", item_code="SR-08", quantity="20",
                  unit_price="400.00", tax_rate="18", tax_amount="1440.00", line_total="9440.00")
    )
    invoice.total_amount = None
    report = match_invoice_to_po(po, invoice)
    assert report.status == MatchStatus.REVIEW
    assert report.discrepancies
    assert report.review_reasons


# ---------------------------------------------------------------------------
# pair_line_items — isolated tests of the matching algorithm (section 6.3)
# ---------------------------------------------------------------------------

def test_pair_line_items_matches_by_item_code():
    po_items = [LineItem(description="Widget A", item_code="A1", quantity="1", unit_price="10.00")]
    inv_items = [LineItem(description="Completely different text", item_code="A1", quantity="1", unit_price="10.00")]
    confident, ambiguous, unmatched_po, unmatched_inv = pair_line_items(po_items, inv_items)
    assert len(confident) == 1
    assert not ambiguous and not unmatched_po and not unmatched_inv


def test_pair_line_items_matches_by_description_when_no_code():
    po_items = [LineItem(description="Widget A", quantity="1", unit_price="10.00")]
    inv_items = [LineItem(description="  widget a  ", quantity="1", unit_price="10.00")]
    confident, ambiguous, unmatched_po, unmatched_inv = pair_line_items(po_items, inv_items)
    assert len(confident) == 1
    assert not ambiguous and not unmatched_po and not unmatched_inv


def test_pair_line_items_ambiguous_when_only_qty_and_price_match():
    po_items = [LineItem(description="Widget A", quantity="1", unit_price="10.00")]
    inv_items = [LineItem(description="Something else entirely", quantity="1", unit_price="10.00")]
    confident, ambiguous, unmatched_po, unmatched_inv = pair_line_items(po_items, inv_items)
    assert not confident
    assert len(ambiguous) == 1
    assert not unmatched_po and not unmatched_inv


def test_pair_line_items_unmatched_on_both_sides_when_nothing_overlaps():
    po_items = [LineItem(description="Widget A", quantity="1", unit_price="10.00")]
    inv_items = [LineItem(description="Widget B", quantity="2", unit_price="20.00")]
    confident, ambiguous, unmatched_po, unmatched_inv = pair_line_items(po_items, inv_items)
    assert not confident and not ambiguous
    assert len(unmatched_po) == 1
    assert len(unmatched_inv) == 1
