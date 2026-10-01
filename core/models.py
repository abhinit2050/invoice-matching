from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum

from pydantic import BaseModel, field_validator


def to_decimal(value: str | int | float | Decimal | None) -> Decimal | None:
    """Convert an LLM-extracted amount to Decimal. Missing/blank values stay None
    rather than being invented; never coerce through float."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        value = value.strip().replace(",", "").replace("$", "").replace("₹", "")
        if value == "":
            return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Cannot convert {value!r} to Decimal") from exc


_MONEY_FIELDS = ("quantity", "unit_price", "discount", "tax_rate", "tax_amount", "line_total")


class LineItem(BaseModel):
    description: str | None = None
    item_code: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    discount: Decimal | None = None
    tax_rate: Decimal | None = None
    tax_amount: Decimal | None = None
    line_total: Decimal | None = None

    @field_validator(*_MONEY_FIELDS, mode="before")
    @classmethod
    def _parse_decimal(cls, value):
        return to_decimal(value)


class PurchaseOrder(BaseModel):
    po_number: str | None = None
    po_date: date | None = None
    vendor_name: str | None = None
    currency: str | None = None
    line_items: list[LineItem] = []
    subtotal: Decimal | None = None
    total_amount: Decimal | None = None
    unreliable_fields: list[str] = []  # field names the LLM extraction was not confident about

    @field_validator("subtotal", "total_amount", mode="before")
    @classmethod
    def _parse_decimal(cls, value):
        return to_decimal(value)


class Invoice(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    po_number: str | None = None
    vendor_name: str | None = None
    currency: str | None = None
    line_items: list[LineItem] = []
    subtotal: Decimal | None = None
    additional_charges: Decimal | None = None
    total_amount: Decimal | None = None
    unreliable_fields: list[str] = []  # field names the LLM extraction was not confident about

    @field_validator("subtotal", "additional_charges", "total_amount", mode="before")
    @classmethod
    def _parse_decimal(cls, value):
        return to_decimal(value)


class CheckStatus(str, Enum):
    PASS_ = "PASS"
    DISCREPANCY = "DISCREPANCY"
    REVIEW = "REVIEW"


class CheckResult(BaseModel):
    check_name: str
    status: CheckStatus
    explanation: str | None = None


class MatchStatus(str, Enum):
    PASS_ = "PASS"
    REVIEW = "REVIEW"


class MatchReport(BaseModel):
    status: MatchStatus
    invoice_number: str | None = None
    po_number: str | None = None
    vendor_name: str | None = None
    checks: list[CheckResult] = []
    discrepancies: list[str] = []  # explanations from checks that found a confirmed mismatch
    review_reasons: list[str] = []  # explanations from checks that couldn't be confidently compared
