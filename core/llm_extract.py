from __future__ import annotations

import os
from datetime import date

from openai import OpenAI
from pydantic import BaseModel

from core.models import Invoice, PurchaseOrder

DEFAULT_MODEL = "gpt-4o-2024-08-06"

SYSTEM_PROMPT = """You are a precise document-data extraction engine for a two-way \
invoice/purchase-order matching system.

Rules:
- Extract ONLY fields that are explicitly present in the document text.
- If a field is not present, return null for it. Never guess, infer, or calculate a \
missing value (e.g. never compute a total from line items if it isn't printed).
- Money amounts must be returned as plain decimal strings (e.g. "500.00"), with no \
currency symbols or thousands separators.
- Dates must be returned in YYYY-MM-DD format.
- If you extracted a value but are not fully confident it is correct (e.g. ambiguous \
OCR-like text, unclear formatting), still return your best-effort value but add that \
field's name to `unreliable_fields`.
"""


class _RawLineItem(BaseModel):
    description: str | None = None
    item_code: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    discount: str | None = None
    tax_rate: str | None = None
    tax_amount: str | None = None
    line_total: str | None = None


class _RawPurchaseOrder(BaseModel):
    po_number: str | None = None
    po_date: date | None = None
    vendor_name: str | None = None
    currency: str | None = None
    line_items: list[_RawLineItem] = []
    subtotal: str | None = None
    total_amount: str | None = None
    unreliable_fields: list[str] = []


class _RawInvoice(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    po_number: str | None = None
    vendor_name: str | None = None
    currency: str | None = None
    line_items: list[_RawLineItem] = []
    subtotal: str | None = None
    additional_charges: str | None = None
    total_amount: str | None = None
    unreliable_fields: list[str] = []


class LLMExtractionError(Exception):
    """Raised when the LLM call fails or returns nothing usable."""


def _client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise LLMExtractionError("OPENAI_API_KEY is not set (check your .env).")
    return OpenAI(api_key=api_key)


def _extract_raw(text: str, schema: type[BaseModel], doc_label: str, model: str) -> BaseModel:
    client = _client()
    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract structured data from this {doc_label} text:\n\n{text}"},
            ],
            response_format=schema,
        )
    except Exception as exc:  # noqa: BLE001 - surface any API/network failure clearly
        raise LLMExtractionError(f"OpenAI extraction failed for {doc_label}: {exc}") from exc

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise LLMExtractionError(f"Model returned no parsed data for {doc_label}.")
    return parsed


def extract_purchase_order(text: str, model: str = DEFAULT_MODEL) -> PurchaseOrder:
    raw = _extract_raw(text, _RawPurchaseOrder, "purchase order", model)
    return PurchaseOrder(**raw.model_dump())


def extract_invoice(text: str, model: str = DEFAULT_MODEL) -> Invoice:
    raw = _extract_raw(text, _RawInvoice, "invoice", model)
    return Invoice(**raw.model_dump())
