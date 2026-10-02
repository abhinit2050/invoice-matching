import pytest

from core.models import Invoice, LineItem, PurchaseOrder


@pytest.fixture
def po() -> PurchaseOrder:
    return PurchaseOrder(
        po_number="PO-1001",
        po_date="2026-01-05",
        vendor_name="Acme Supplies Pvt Ltd",
        currency="INR",
        line_items=[
            LineItem(description="Steel Rod 10mm", item_code="SR-10", quantity="100",
                      unit_price="500.00", discount="0.00", tax_rate="18",
                      tax_amount="9000.00", line_total="59000.00"),
            LineItem(description="Steel Rod 12mm", item_code="SR-12", quantity="50",
                      unit_price="650.00", discount="0.00", tax_rate="18",
                      tax_amount="5850.00", line_total="38350.00"),
        ],
        subtotal="82500.00",
        total_amount="97350.00",
    )


@pytest.fixture
def invoice() -> Invoice:
    return Invoice(
        invoice_number="INV-2001",
        invoice_date="2026-01-10",
        po_number="PO-1001",
        vendor_name="Acme Supplies Pvt Ltd",
        currency="INR",
        line_items=[
            LineItem(description="Steel Rod 10mm", item_code="SR-10", quantity="100",
                      unit_price="500.00", discount="0.00", tax_rate="18",
                      tax_amount="9000.00", line_total="59000.00"),
            LineItem(description="Steel Rod 12mm", item_code="SR-12", quantity="50",
                      unit_price="650.00", discount="0.00", tax_rate="18",
                      tax_amount="5850.00", line_total="38350.00"),
        ],
        subtotal="82500.00",
        additional_charges="0.00",
        total_amount="97350.00",
    )
