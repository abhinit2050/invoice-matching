# 3-Day Build Plan

Deployment target: Streamlit Community Cloud demo (sample documents only, API key in app secrets).
Principle: build bottom-up and test each layer on its own before wiring it into LangGraph.

## Day 1 - Data in (models, PDFs, extraction)

1. Setup (30 min): repo, venv, requirements.txt, .env with OPENAI_API_KEY, .gitignore.
2. Pydantic models (2 hrs): PO and Invoice schemas per spec section 5.
   - Optional fields default to None; money is Decimal.
   - LLM returns money as strings; validators convert to Decimal.
   - Add `unreliable_fields: list[str]` so the LLM can flag uncertain values.
3. Sample PDF generator (2 hrs): scripts/make_samples.py builds PO/invoice pairs
   from Python dicts with reportlab, one pair per test scenario (spec section 13).
4. PDF text extraction (1 hr): PyMuPDF wrapper that returns clear errors for
   empty, encrypted, or non-PDF files instead of raising.
5. LLM extraction (2 hrs): OpenAI structured outputs using the Pydantic model.
   Prompt: return null for anything absent; never calculate missing values.

Done when: extracting a sample PO and invoice prints valid Pydantic objects with correct Decimal values.

## Day 2 - Logic (matching engine, LangGraph)

1. Matching engine (4 hrs): pure functions in core/matching.py, one per check in spec section 6:
   vendor, PO reference, line-item pairing (SKU first, then normalized description),
   quantity, unit price, discount, tax, total.
   - Each returns a CheckResult: PASS / DISCREPANCY / REVIEW + explanation.
   - Overall status derived from the checks; REVIEW can never become MATCHED.
   - Decide and document precedence when both DISCREPANCY and REVIEW occur.
2. Unit tests (1.5 hrs): test matching with hand-built Pydantic objects (no PDFs, no LLM).
3. LangGraph workflow (2.5 hrs):
   - State as TypedDict with the fields from spec section 8.2.
   - Each node returns only the keys it changes.
   - Conditional edge after validation: needs_review vs match.
   - Stretch: PO and invoice extraction as parallel nodes joining at validation.

Done when: graph.invoke() on a sample pair returns a full report in the terminal and pytest passes.

## Day 3 - UI, end-to-end testing, deployment

1. Streamlit UI (3 hrs):
   - Upload screen: two uploaders; button disabled until both files are present.
   - Processing: run graph.stream() and update st.status as each node finishes.
   - Results: line-item comparison table, discrepancy list, raw extracted JSON in an expander.
   - Review screen: flagged fields, extracted values, and why each was flagged.
2. End-to-end run of all 14 scenarios (2 hrs): fix extraction quirks via prompt tweaks.
3. Deploy (1 hr): push to GitHub, connect in Streamlit Community Cloud, add OPENAI_API_KEY to secrets.
4. Buffer: whatever slipped.

Done when: the deployed URL accepts two PDFs and produces the correct status for all 14 scenarios.

## If time runs short
Cut first: parallel extraction nodes, review-screen polish.
Never cut: the deterministic matching engine and its tests.
