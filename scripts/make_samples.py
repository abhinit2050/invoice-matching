"""Generates matched PO/invoice PDF pairs for the 14 test scenarios in docs/specs.md section 13."""

from __future__ import annotations

import shutil
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
STYLES = getSampleStyleSheet()
TWO_PLACES = Decimal("0.01")


def money(value) -> str:
    return str(Decimal(value).quantize(TWO_PLACES))


def _line(description, item_code, quantity, unit_price, tax_rate, discount="0.00") -> dict:
    quantity, unit_price, discount, tax_rate = (
        Decimal(quantity), Decimal(unit_price), Decimal(discount), Decimal(tax_rate)
    )
    pretax = quantity * unit_price - discount
    tax_amount = (pretax * tax_rate / 100).quantize(TWO_PLACES)
    return {
        "description": description,
        "item_code": item_code,
        "quantity": str(quantity),
        "unit_price": money(unit_price),
        "discount": money(discount),
        "tax_rate": str(tax_rate),
        "tax_amount": money(tax_amount),
        "line_total": money(pretax + tax_amount),
    }


def _totals(line_items: list[dict], additional_charges: str = "0.00") -> dict:
    subtotal = sum(
        (Decimal(li["quantity"]) * Decimal(li["unit_price"]) - Decimal(li["discount"])) for li in line_items
    )
    tax_total = sum(Decimal(li["tax_amount"]) for li in line_items)
    additional_charges = Decimal(additional_charges)
    return {
        "subtotal": money(subtotal),
        "tax_total": money(tax_total),
        "additional_charges": money(additional_charges),
        "total_amount": money(subtotal + tax_total + additional_charges),
    }


BASE_LINE_ITEMS = [
    _line("Steel Rod 10mm", "SR-10", "100", "500.00", "18"),
    _line("Steel Rod 12mm", "SR-12", "50", "650.00", "18"),
]

BASE_HEADER = {
    "po_number": "PO-1001",
    "po_date": "2026-01-05",
    "invoice_number": "INV-2001",
    "invoice_date": "2026-01-10",
    "vendor_name": "Acme Supplies Pvt Ltd",
    "currency": "INR",
}


def base_po() -> dict:
    return {
        "doc_type": "PURCHASE ORDER",
        "po_number": BASE_HEADER["po_number"],
        "po_date": BASE_HEADER["po_date"],
        "vendor_name": BASE_HEADER["vendor_name"],
        "currency": BASE_HEADER["currency"],
        "line_items": deepcopy(BASE_LINE_ITEMS),
    }


def base_invoice() -> dict:
    return {
        "doc_type": "INVOICE",
        "invoice_number": BASE_HEADER["invoice_number"],
        "invoice_date": BASE_HEADER["invoice_date"],
        "po_number": BASE_HEADER["po_number"],
        "vendor_name": BASE_HEADER["vendor_name"],
        "currency": BASE_HEADER["currency"],
        "line_items": deepcopy(BASE_LINE_ITEMS),
        "additional_charges": "0.00",
    }


def render_pdf(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if doc.get("blank_page"):
        SimpleDocTemplate(str(path), pagesize=letter).build([Spacer(1, 1)])
        return

    is_invoice = doc["doc_type"] == "INVOICE"
    line_items = doc["line_items"]
    totals = _totals(line_items, doc.get("additional_charges", "0.00"))

    elements = [Paragraph(doc["doc_type"], STYLES["Title"]), Spacer(1, 12)]

    if is_invoice:
        header_lines = [
            f"Invoice Number: {doc.get('invoice_number', '')}",
            f"Invoice Date: {doc.get('invoice_date', '')}",
            f"PO Reference: {doc.get('po_number', '')}",
        ]
    else:
        header_lines = [
            f"PO Number: {doc.get('po_number', '')}",
            f"PO Date: {doc.get('po_date', '')}",
        ]
    header_lines += [f"Vendor: {doc.get('vendor_name', '')}", f"Currency: {doc.get('currency', '')}"]
    for line in header_lines:
        elements.append(Paragraph(line, STYLES["Normal"]))
    elements.append(Spacer(1, 12))

    table_data = [["Description", "Item Code", "Qty", "Unit Price", "Discount", "Tax Rate %", "Tax Amount", "Line Total"]]
    for li in line_items:
        table_data.append([
            li.get("description", ""), li.get("item_code", ""), li.get("quantity", ""),
            li.get("unit_price", ""), li.get("discount", ""), li.get("tax_rate", ""),
            li.get("tax_amount", ""), li.get("line_total", ""),
        ])
    table = Table(table_data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(f"Subtotal: {totals['subtotal']}", STYLES["Normal"]))
    elements.append(Paragraph(f"Total Tax: {totals['tax_total']}", STYLES["Normal"]))
    if is_invoice:
        elements.append(Paragraph(f"Additional Charges: {totals['additional_charges']}", STYLES["Normal"]))
    total_amount = doc.get("total_amount_override", totals["total_amount"])
    elements.append(Paragraph(f"Total Amount: {total_amount}", STYLES["Normal"]))

    SimpleDocTemplate(str(path), pagesize=letter).build(elements)


# ---------------------------------------------------------------------------
# Scenarios (docs/specs.md section 13)
# ---------------------------------------------------------------------------

def scenario_01_exact_match():
    return base_po(), base_invoice()


def scenario_02_higher_unit_price():
    inv = base_invoice()
    inv["line_items"][0] = _line("Steel Rod 10mm", "SR-10", "100", "550.00", "18")
    return base_po(), inv


def scenario_03_lower_unit_price():
    inv = base_invoice()
    inv["line_items"][0] = _line("Steel Rod 10mm", "SR-10", "100", "450.00", "18")
    return base_po(), inv


def scenario_04_quantity_exceeds_po():
    inv = base_invoice()
    inv["line_items"][0] = _line("Steel Rod 10mm", "SR-10", "120", "500.00", "18")
    return base_po(), inv


def scenario_05_quantity_below_po():
    inv = base_invoice()
    inv["line_items"][0] = _line("Steel Rod 10mm", "SR-10", "80", "500.00", "18")
    return base_po(), inv


def scenario_06_unexpected_line_item():
    inv = base_invoice()
    inv["line_items"].append(_line("Steel Rod 8mm", "SR-08", "20", "400.00", "18"))
    return base_po(), inv


def scenario_07_wrong_po_reference():
    inv = base_invoice()
    inv["po_number"] = "PO-9999"
    return base_po(), inv


def scenario_08_vendor_mismatch():
    inv = base_invoice()
    inv["vendor_name"] = "Acme Supply Co."
    return base_po(), inv


def scenario_09_tax_discrepancy():
    inv = base_invoice()
    inv["line_items"][0] = _line("Steel Rod 10mm", "SR-10", "100", "500.00", "12")
    return base_po(), inv


def scenario_10_discount_discrepancy():
    inv = base_invoice()
    inv["line_items"][0] = _line("Steel Rod 10mm", "SR-10", "100", "500.00", "18", discount="2000.00")
    return base_po(), inv


def scenario_11_missing_required_fields():
    inv = base_invoice()
    inv["invoice_number"] = ""
    inv["line_items"][1]["item_code"] = ""
    inv["total_amount_override"] = ""
    return base_po(), inv


def scenario_12_unconfident_line_item_match():
    inv = base_invoice()
    inv["line_items"][0] = _line("10mm rebar (misc grade, unspecified alloy)", "", "100", "500.00", "18")
    return base_po(), inv


def scenario_13_unreadable_invoice():
    inv = base_invoice()
    inv["blank_page"] = True
    return base_po(), inv


def scenario_14_total_amount_mismatch():
    inv = base_invoice()
    correct_total = Decimal(_totals(inv["line_items"], inv["additional_charges"])["total_amount"])
    inv["total_amount_override"] = money(correct_total + Decimal("500.00"))
    return base_po(), inv


SCENARIOS = [
    ("01_exact_match", scenario_01_exact_match, "Invoice and PO match completely."),
    ("02_higher_unit_price", scenario_02_higher_unit_price, "Invoice contains a higher unit price."),
    ("03_lower_unit_price", scenario_03_lower_unit_price, "Invoice contains a lower unit price."),
    ("04_quantity_exceeds_po", scenario_04_quantity_exceeds_po, "Invoice quantity exceeds the ordered quantity."),
    ("05_quantity_below_po", scenario_05_quantity_below_po, "Invoice quantity is lower than the ordered quantity."),
    ("06_unexpected_line_item", scenario_06_unexpected_line_item, "Invoice contains an unexpected line item."),
    ("07_wrong_po_reference", scenario_07_wrong_po_reference, "Invoice references an incorrect PO number."),
    ("08_vendor_mismatch", scenario_08_vendor_mismatch, "Vendor names differ."),
    ("09_tax_discrepancy", scenario_09_tax_discrepancy, "Invoice contains a tax discrepancy."),
    ("10_discount_discrepancy", scenario_10_discount_discrepancy, "Invoice contains a discount discrepancy."),
    ("11_missing_required_fields", scenario_11_missing_required_fields, "Required fields are missing."),
    ("12_unconfident_line_item_match", scenario_12_unconfident_line_item_match, "A line item cannot be matched confidently."),
    ("13_unreadable_invoice", scenario_13_unreadable_invoice, "A PDF is unreadable (no extractable text)."),
    ("14_total_amount_mismatch", scenario_14_total_amount_mismatch, "Invoice total does not match the calculated expected total."),
]


def main() -> None:
    if SAMPLES_DIR.exists():
        shutil.rmtree(SAMPLES_DIR)
    SAMPLES_DIR.mkdir(parents=True)

    manifest = ["# Generated sample scenarios\n"]
    for slug, builder, description in SCENARIOS:
        po_doc, invoice_doc = builder()
        scenario_dir = SAMPLES_DIR / slug
        render_pdf(scenario_dir / "po.pdf", po_doc)
        render_pdf(scenario_dir / "invoice.pdf", invoice_doc)
        manifest.append(f"- **{slug}**: {description}")
        print(f"Generated {slug}: {description}")

    (SAMPLES_DIR / "MANIFEST.md").write_text("\n".join(manifest) + "\n")


if __name__ == "__main__":
    main()
