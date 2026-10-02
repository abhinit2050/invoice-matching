r"""LangGraph workflow (docs/specs.md section 8).

START
  |-- extract_po_text ------> extract_po_data ------\
  |                                                   >-- validate --(cond)--> run_matching_checks -> identify_discrepancies -> generate_report -> END
  \-- extract_invoice_text -> extract_invoice_data --/                  \
                                                                          \--> build_needs_review_report -> END

PO and invoice extraction run as parallel branches (stretch goal in
docs/plan.md Day 2 step 3) and join at `validate`. The conditional edge after
validation routes invalid extractions straight to a REVIEW report, skipping
the matching engine entirely.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from core.llm_extract import LLMExtractionError, extract_invoice, extract_purchase_order
from core.matching import derive_overall_status, run_checks, split_checks
from core.models import MatchReport, MatchStatus
from core.pdf_text import extract_text
from graph.state import GraphState


# ---------------------------------------------------------------------------
# Nodes 1-3: PDF text extraction, PO/invoice structured data extraction
# ---------------------------------------------------------------------------

def extract_po_text(state: GraphState) -> dict:
    result = extract_text(state["po_path"])
    if not result.ok:
        return {"po_text_error": result.error}
    return {"po_text": result.text}


def extract_invoice_text(state: GraphState) -> dict:
    result = extract_text(state["invoice_path"])
    if not result.ok:
        return {"invoice_text_error": result.error}
    return {"invoice_text": result.text}


def extract_po_data(state: GraphState) -> dict:
    if state.get("po_text_error"):
        return {}
    try:
        return {"po_data": extract_purchase_order(state["po_text"])}
    except LLMExtractionError as exc:
        return {"po_data_error": str(exc)}


def extract_invoice_data(state: GraphState) -> dict:
    if state.get("invoice_text_error"):
        return {}
    try:
        return {"invoice_data": extract_invoice(state["invoice_text"])}
    except LLMExtractionError as exc:
        return {"invoice_data_error": str(exc)}


# ---------------------------------------------------------------------------
# Node 4: validation + conditional routing
# ---------------------------------------------------------------------------

def validate(state: GraphState) -> dict:
    errors = [
        e for e in (
            state.get("po_text_error"),
            state.get("invoice_text_error"),
            state.get("po_data_error"),
            state.get("invoice_data_error"),
        ) if e
    ]
    if not errors and state.get("po_data") is None:
        errors.append("PO data extraction did not return a result.")
    if not errors and state.get("invoice_data") is None:
        errors.append("Invoice data extraction did not return a result.")
    return {"validation_errors": errors}


def route_after_validation(state: GraphState) -> str:
    return "needs_review" if state.get("validation_errors") else "match"


def build_needs_review_report(state: GraphState) -> dict:
    po_data, invoice_data = state.get("po_data"), state.get("invoice_data")
    report = MatchReport(
        status=MatchStatus.REVIEW,
        invoice_number=invoice_data.invoice_number if invoice_data else None,
        po_number=po_data.po_number if po_data else None,
        vendor_name=(invoice_data.vendor_name if invoice_data else None)
        or (po_data.vendor_name if po_data else None),
        review_reasons=list(state.get("validation_errors", [])),
    )
    return {"report": report}


# ---------------------------------------------------------------------------
# Nodes 5-7: matching, discrepancy identification, report generation
# ---------------------------------------------------------------------------

def run_matching_checks(state: GraphState) -> dict:
    return {"checks": run_checks(state["po_data"], state["invoice_data"])}


def identify_discrepancies(state: GraphState) -> dict:
    discrepancies, review_reasons = split_checks(state["checks"])
    return {"discrepancies": discrepancies, "review_reasons": review_reasons}


def generate_report(state: GraphState) -> dict:
    po_data, invoice_data = state["po_data"], state["invoice_data"]
    report = MatchReport(
        status=derive_overall_status(state["discrepancies"], state["review_reasons"]),
        invoice_number=invoice_data.invoice_number,
        po_number=po_data.po_number,
        vendor_name=invoice_data.vendor_name or po_data.vendor_name,
        checks=state["checks"],
        discrepancies=state["discrepancies"],
        review_reasons=state["review_reasons"],
    )
    return {"report": report}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("extract_po_text", extract_po_text)
    graph.add_node("extract_invoice_text", extract_invoice_text)
    graph.add_node("extract_po_data", extract_po_data)
    graph.add_node("extract_invoice_data", extract_invoice_data)
    graph.add_node("validate", validate)
    graph.add_node("build_needs_review_report", build_needs_review_report)
    graph.add_node("run_matching_checks", run_matching_checks)
    graph.add_node("identify_discrepancies", identify_discrepancies)
    graph.add_node("generate_report", generate_report)

    graph.add_edge(START, "extract_po_text")
    graph.add_edge(START, "extract_invoice_text")
    graph.add_edge("extract_po_text", "extract_po_data")
    graph.add_edge("extract_invoice_text", "extract_invoice_data")
    graph.add_edge("extract_po_data", "validate")
    graph.add_edge("extract_invoice_data", "validate")

    graph.add_conditional_edges(
        "validate",
        route_after_validation,
        {"needs_review": "build_needs_review_report", "match": "run_matching_checks"},
    )

    graph.add_edge("build_needs_review_report", END)
    graph.add_edge("run_matching_checks", "identify_discrepancies")
    graph.add_edge("identify_discrepancies", "generate_report")
    graph.add_edge("generate_report", END)

    return graph


def compile_graph():
    return build_graph().compile()
