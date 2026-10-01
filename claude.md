# AI-Powered Invoice Matching System

Two-way matching of a vendor invoice against a purchase order (PO).
An LLM extracts structured data from PDFs; deterministic Python code does the matching.
Primary learning goal: LangGraph.

Spec: @docs/specs.md
Build plan: @docs/plan.md

## Stack
Python 3, Streamlit, LangGraph, OpenAI API (structured outputs), PyMuPDF, Pydantic, Decimal, reportlab (sample PDFs), pytest.

## Project layout
- app.py               Streamlit UI
- core/models.py       Pydantic models (PO, Invoice, LineItem, CheckResult, MatchReport)
- core/pdf_text.py     PyMuPDF text extraction + unreadable/empty PDF detection
- core/llm_extract.py  OpenAI -> Pydantic structured extraction
- core/matching.py     Deterministic matching rules (no LLM)
- core/config.py       Configurable quantity/price tolerances
- graph/state.py       LangGraph state (TypedDict)
- graph/workflow.py    Nodes, edges, conditional routing
- scripts/make_samples.py  Generates PO/invoice PDF pairs for the test scenarios
- samples/             Generated PDFs
- tests/               pytest tests

## Non-negotiable rules
- Money is always Decimal, never float. The LLM returns amounts as strings; convert in Pydantic validators.
- The LLM only extracts data. It never decides the overall match status.
- Never invent or calculate missing financial values during extraction; keep them None.
- Overall match status is PASS or REVIEW only (docs/specs.md section 7). Any confirmed
  discrepancy or any inconclusive comparison must never resolve to PASS; when a match has
  both, the REVIEW report explains both.
- Errors are reported clearly and never crash the app.
- Out of scope: RAG, databases, auth, OCR, three-way matching, ERP integration.

## Commands
- Setup: python3 -m venv .venv && source .venv/bin/activate && pip3 install -r requirements.txt
- Tests: pytest
- Run app: streamlit run app.py
- API key: OPENAI_API_KEY in .env (never commit it)

## Working style
- I am learning LangGraph and building up my Python; I know JavaScript and Linux well.
  Where a concept is new, a brief JavaScript/Linux analogy helps.
- Work one plan step at a time. List the sub-steps first, then stop after each
  step and wait for me to confirm it works before continuing.
- Keep changes small and explain what each new file or function does.
