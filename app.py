"""Streamlit UI (docs/specs.md section 9)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from core.matching import pair_line_items
from core.models import Invoice, MatchStatus, PurchaseOrder
from graph.workflow import compile_graph

st.set_page_config(page_title="Invoice Matching System", page_icon="🧾", layout="wide")
st.title("AI-Powered Invoice Matching System")
st.caption("Two-way matching of a vendor invoice against a purchase order. LLM extracts; deterministic code matches.")

if "graph" not in st.session_state:
    st.session_state.graph = compile_graph()

NODE_LABELS = {
    "extract_po_text": "Extracting PO PDF text",
    "extract_invoice_text": "Extracting invoice PDF text",
    "extract_po_data": "Extracting structured PO data",
    "extract_invoice_data": "Extracting structured invoice data",
    "validate": "Validating extracted data",
    "build_needs_review_report": "Building review report",
    "run_matching_checks": "Matching invoice against PO",
    "identify_discrepancies": "Identifying discrepancies",
    "generate_report": "Generating matching report",
}


def _save_to_temp(uploaded_file) -> str:
    suffix = Path(uploaded_file.name).suffix or ".pdf"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.getvalue())
    tmp.close()
    return tmp.name


def _line_item_rows(po_data: PurchaseOrder, invoice_data: Invoice) -> list[dict]:
    confident, ambiguous, unmatched_po, unmatched_invoice = pair_line_items(
        po_data.line_items, invoice_data.line_items
    )
    rows = []
    for po_item, inv_item in confident:
        matched = po_item.quantity == inv_item.quantity and po_item.unit_price == inv_item.unit_price
        rows.append({
            "Item": po_item.item_code or po_item.description,
            "PO Qty": po_item.quantity, "Invoice Qty": inv_item.quantity,
            "PO Unit Price": po_item.unit_price, "Invoice Unit Price": inv_item.unit_price,
            "PO Tax": po_item.tax_amount, "Invoice Tax": inv_item.tax_amount,
            "Status": "Match" if matched else "Mismatch",
        })
    for po_item, inv_item in ambiguous:
        rows.append({
            "Item": f"{po_item.description} / {inv_item.description}",
            "PO Qty": po_item.quantity, "Invoice Qty": inv_item.quantity,
            "PO Unit Price": po_item.unit_price, "Invoice Unit Price": inv_item.unit_price,
            "PO Tax": po_item.tax_amount, "Invoice Tax": inv_item.tax_amount,
            "Status": "Ambiguous match",
        })
    for po_item in unmatched_po:
        rows.append({
            "Item": po_item.item_code or po_item.description,
            "PO Qty": po_item.quantity, "Invoice Qty": None,
            "PO Unit Price": po_item.unit_price, "Invoice Unit Price": None,
            "PO Tax": po_item.tax_amount, "Invoice Tax": None,
            "Status": "Missing from invoice",
        })
    for inv_item in unmatched_invoice:
        rows.append({
            "Item": inv_item.item_code or inv_item.description,
            "PO Qty": None, "Invoice Qty": inv_item.quantity,
            "PO Unit Price": None, "Invoice Unit Price": inv_item.unit_price,
            "PO Tax": None, "Invoice Tax": inv_item.tax_amount,
            "Status": "Unexpected line item",
        })
    return rows


# ---------------------------------------------------------------------------
# Upload screen (9.1)
# ---------------------------------------------------------------------------

col1, col2 = st.columns(2)
with col1:
    po_file = st.file_uploader("Purchase Order (PDF)", type="pdf", key="po_file")
with col2:
    invoice_file = st.file_uploader("Invoice (PDF)", type="pdf", key="invoice_file")

run_disabled = po_file is None or invoice_file is None
run_clicked = st.button("Match Invoice to PO", disabled=run_disabled, type="primary")

# ---------------------------------------------------------------------------
# Processing screen (9.2)
# ---------------------------------------------------------------------------

if run_clicked:
    po_path = _save_to_temp(po_file)
    invoice_path = _save_to_temp(invoice_file)

    final_state: dict = {}
    with st.status("Processing documents...", expanded=True) as status_box:
        for update in st.session_state.graph.stream({"po_path": po_path, "invoice_path": invoice_path}):
            for node_name, node_update in update.items():
                st.write(f"✅ {NODE_LABELS.get(node_name, node_name)}")
                final_state.update(node_update)
        status_box.update(label="Done", state="complete")

    st.session_state.result = final_state

# ---------------------------------------------------------------------------
# Results / Review screens (9.3 / 9.4)
# ---------------------------------------------------------------------------

if "result" in st.session_state:
    result = st.session_state.result
    report = result.get("report")
    po_data, invoice_data = result.get("po_data"), result.get("invoice_data")

    st.divider()

    if report is None:
        st.error("No report was generated.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Invoice Number", report.invoice_number or "—")
        m2.metric("PO Number", report.po_number or "—")
        m3.metric("Vendor", report.vendor_name or "—")

        if report.status == MatchStatus.PASS_:
            st.success("PASS — all checks passed within tolerance.")
        else:
            st.warning("REVIEW — see details below.")

        if report.discrepancies:
            st.markdown("### Discrepancies")
            for d in report.discrepancies:
                st.markdown(f"- {d}")

        if report.review_reasons:
            st.markdown("### Needs Review")
            for r in report.review_reasons:
                st.markdown(f"- {r}")

        if po_data is not None and invoice_data is not None:
            st.markdown("### Line-Item Comparison")
            st.dataframe(_line_item_rows(po_data, invoice_data), use_container_width=True)

        with st.expander("Raw extracted data (JSON)"):
            ec1, ec2 = st.columns(2)
            with ec1:
                st.markdown("**Purchase Order**")
                st.json(po_data.model_dump(mode="json") if po_data else {})
            with ec2:
                st.markdown("**Invoice**")
                st.json(invoice_data.model_dump(mode="json") if invoice_data else {})
