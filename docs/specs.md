# Project Specifications: AI-Powered Invoice Matching System

## 1. Project Overview

Build an AI-powered invoice matching system that compares vendor invoices against purchase orders (POs) to identify discrepancies in quantities, prices, taxes, and other details.

The system will use an LLM to extract structured information from PDF documents and deterministic business logic to perform the actual matching.

### Project Objectives

- Build a functional two-way invoice matching system.
- Learn LangGraph through a practical business workflow.
- Understand LLM-based structured data extraction and validation.
- Implement conditional routing and error handling using LangGraph.
- Build a simple user interface using Streamlit.
- Complete a functional MVP within 3–4 days.

### Learning Focus

The primary learning focus is LangGraph and its application in orchestrating multi-step AI workflows.

RAG is explicitly excluded from this version.

---

## 2. Scope

### In Scope

- Two-way matching between a purchase order and an invoice.
- PDF document processing.
- Support for realistic business invoices containing multiple line items, taxes, discounts, and totals.
- LLM-based structured data extraction.
- Deterministic matching and discrepancy detection.
- A Streamlit-based user interface.
- LangGraph-based workflow orchestration.
- Error handling and human review for uncertain extractions.

### Out of Scope

- Three-way matching using Goods Receipt Notes (GRNs).
- RAG and vector databases.
- Database integration.
- User authentication and authorization.
- Multiple invoices matched against a single PO.
- Automated payment processing.
- ERP integration.
- Production deployment and enterprise-grade security.
- OCR for scanned PDFs in the initial version.

---

## 3. Two-Way Matching

The system compares two documents:

1. **Purchase Order (PO):** Specifies the products or services ordered from a vendor, including quantities and agreed prices.
2. **Vendor Invoice:** Specifies the products or services being billed by the vendor.

The system checks whether the invoice is consistent with the purchase order.

### Example

| Field | Purchase Order | Invoice |
|---|---:|---:|
| Product A Quantity | 100 | 100 |
| Unit Price | ₹500 | ₹550 |
| Subtotal | ₹50,000 | ₹55,000 |

The system should identify the unit price discrepancy and flag the invoice for review.

---

## 4. Input Documents

The application must accept:

- One purchase order PDF.
- One vendor invoice PDF.

### Document Requirements

- PDFs should contain selectable text.
- Documents may contain multiple pages.
- Documents may contain multiple line items.
- Documents may include taxes, discounts, and other charges.

The system should reject unsupported or unreadable files with a clear error message.

---

## 5. Document Data Extraction

The system must extract structured information from both documents.

An LLM will be used to convert the extracted document text into structured JSON.

### 5.1 Purchase Order Fields

| Field | Description |
|---|---|
| PO Number | Unique purchase order identifier |
| PO Date | Date of purchase order |
| Vendor Name | Name of the supplier |
| Currency | Currency used in the PO |
| Line Items | List of ordered products or services |
| Item Description | Product or service description |
| Item Code / SKU | Product identifier, if available |
| Quantity | Ordered quantity |
| Unit Price | Agreed price per unit |
| Discount | Line-item discount, if available |
| Tax Rate | Applicable tax rate, if available |
| Tax Amount | Tax amount, if available |
| Line Total | Total amount for the line item |
| Subtotal | Total before taxes and additional charges |
| Total Amount | Final PO amount |

### 5.2 Invoice Fields

| Field | Description |
|---|---|
| Invoice Number | Unique invoice identifier |
| Invoice Date | Date of invoice |
| PO Number | Referenced purchase order number |
| Vendor Name | Name of the supplier |
| Currency | Currency used in the invoice |
| Line Items | List of billed products or services |
| Item Description | Product or service description |
| Item Code / SKU | Product identifier, if available |
| Quantity | Invoiced quantity |
| Unit Price | Price charged per unit |
| Discount | Line-item discount, if available |
| Tax Rate | Applicable tax rate, if available |
| Tax Amount | Tax amount, if available |
| Line Total | Total amount for the line item |
| Subtotal | Total before taxes and additional charges |
| Additional Charges | Shipping, handling, and other charges |
| Total Amount | Final invoice amount |

### Extraction Requirements

- Use Pydantic models to validate extracted data.
- Represent monetary amounts using decimal arithmetic.
- Preserve missing fields as null rather than inventing values.
- Identify fields that could not be extracted reliably.
- Return structured validation errors when required fields are missing.

---

## 6. Matching Engine

The matching engine must compare the extracted PO and invoice data using deterministic business rules.

The LLM must not independently decide whether an invoice should be approved or rejected.

### 6.1 Vendor Matching

Compare the vendor names on the PO and invoice.

- Exact matches should pass.
- Differences in capitalization and whitespace should be ignored.
- Potentially equivalent but different names should be flagged for review.

### 6.2 PO Reference Validation

Check whether the invoice references the correct PO number.

- Matching PO numbers should pass.
- Missing or conflicting PO numbers should be flagged.

### 6.3 Line-Item Matching

Match invoice line items against PO line items.

Use the following fields in order of preference:

1. Item code or SKU, when available.
2. Normalized item description, when item codes are unavailable.

If a line item cannot be matched confidently, flag it for review.

### 6.4 Quantity Matching

Compare the invoiced quantity against the ordered quantity.

- Exact matches should pass.
- Differences should be flagged.
- Quantity tolerances should be configurable.

### 6.5 Unit Price Matching

Compare the invoiced unit price against the PO unit price.

- Exact matches should pass.
- Differences beyond the configured tolerance should be flagged.
- Price tolerances should be configurable.

### 6.6 Discount Matching

Compare discounts when both documents provide sufficient information.

Flag differences that cannot be reconciled using the available data.

### 6.7 Tax Matching

Compare tax rates and amounts when available.

- Check whether the invoice tax is consistent with the PO tax information.
- Flag discrepancies.
- Do not assume that tax must always be identical between documents.

### 6.8 Total Amount Matching

Compare the invoice total against the expected amount derived from the PO.

Account for:

- Quantities
- Unit prices
- Discounts
- Taxes
- Additional charges, when applicable

If the PO does not contain enough information to calculate an expected total, flag the comparison as requiring review.

---

## 7. Matching Results

The system must classify each matching attempt into one of two statuses.

### PASS

All checks pass within the configured tolerances, and every comparison could be
completed confidently. No further action needed.

### REVIEW

Anything short of a clean PASS — a confirmed discrepancy, an ambiguous
comparison, or both at once. A document requiring review must never be
classified as PASS.

The underlying checks (section 6) still distinguish a confirmed discrepancy
from an inconclusive comparison internally (so the report can explain *why*
review is needed), but both collapse to the single REVIEW status:

- **Confirmed discrepancies** — e.g. unit price mismatch, quantity mismatch,
  incorrect PO reference, unexpected line item, total amount mismatch.
- **Inconclusive comparisons** — e.g. required fields are missing, a line item
  cannot be matched confidently, the document contains ambiguous information,
  the expected total cannot be calculated reliably.

When a match has both kinds of findings, the REVIEW report surfaces both: the
specific discrepancies found, and the specific reasons a human still needs to
look at it.

---

## 8. LangGraph Workflow

The workflow must be implemented using LangGraph.

### 8.1 Workflow Diagram

    START
      |
      v
    Upload Documents
      |
      v
    Extract PDF Text
      |
      v
    Extract Structured Data
      |
      v
    Validate Extracted Data
      |
      +---- Validation Failed ----> Needs Review
      |
      v
    Match Invoice with PO
      |
      v
    Identify Discrepancies
      |
      v
    Generate Matching Report
      |
      v
    END

### 8.2 LangGraph Components

#### State

Maintain the following information throughout the workflow:

- Uploaded document references.
- Extracted PO data.
- Extracted invoice data.
- Validation errors.
- Matching results.
- Discrepancy details.
- Final matching status.
- Error messages.

#### Nodes

Implement separate nodes for:

1. PDF text extraction.
2. PO data extraction.
3. Invoice data extraction.
4. Data validation.
5. Invoice-to-PO matching.
6. Discrepancy identification.
7. Report generation.

#### Conditional Routing

Use conditional edges to:

- Route invalid extractions to the review state.
- Route valid extractions to the matching engine.
- Route matching failures to the appropriate error-handling path.

---

## 9. Streamlit User Interface

Build a simple Streamlit application.

### 9.1 Upload Screen

The interface must provide:

- Purchase order PDF upload.
- Invoice PDF upload.
- A button to initiate matching.

The matching process should begin only after both documents have been uploaded.

### 9.2 Processing Screen

Display the current processing stage:

- Extracting document text.
- Extracting structured data.
- Validating extracted information.
- Matching invoice against PO.
- Generating the report.

### 9.3 Results Screen

Display:

- Invoice number.
- PO number.
- Vendor name.
- Overall matching status.
- Matching summary.
- Line-item comparison table.
- Discrepancies and explanations.
- Extracted document data.

### 9.4 Review Screen

When the overall status is REVIEW:

- Display the confirmed discrepancies, if any (what mismatched and by how much).
- Display the fields that couldn't be confidently compared, if any, and why.
- Show the extracted values.
- Allow the user to inspect the extracted information.

Manual correction and resubmission are optional extensions.

---

## 10. Matching Report

The system must generate a structured matching report.

### Example

**Overall Status:** REVIEW

**Invoice Number:** INV-2026-001

**PO Number:** PO-2026-001

**Vendor:** ABC Supplies

### Line-Item Comparison

| Field | PO | Invoice | Status |
|---|---:|---:|---|
| Quantity | 100 | 100 | Match |
| Unit Price | ₹500 | ₹550 | Mismatch |
| Subtotal | ₹50,000 | ₹55,000 | Mismatch |

### Discrepancies

1. Unit price is ₹50 higher than the PO price.
2. The invoice subtotal exceeds the expected subtotal by ₹5,000.

The report should explain each discrepancy using the extracted values and matching rules.

---

## 11. Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| User Interface | Streamlit |
| Workflow Orchestration | LangGraph |
| LLM Integration | OpenAI API |
| PDF Text Extraction | PyMuPDF |
| Data Validation | Pydantic |
| Monetary Calculations | Python Decimal |
| Initial Storage | In-memory and temporary files |

Use a modular architecture so that document extraction, matching logic, and workflow orchestration can be tested independently.

---

## 12. Error Handling

The system must handle the following situations:

- Invalid PDF files.
- Empty or unreadable PDFs.
- Missing required fields.
- LLM extraction failures.
- Invalid structured output.
- Unmatched line items.
- Missing PO references.
- Unsupported currencies.
- Inconsistent monetary calculations.

Errors should be reported clearly without crashing the application.

The system must never silently assume missing financial values.

---

## 13. Testing Requirements

Test the application using sample invoices and purchase orders.

### Required Test Scenarios

1. Invoice and PO match completely.
2. Invoice contains a higher unit price.
3. Invoice contains a lower unit price.
4. Invoice quantity exceeds the ordered quantity.
5. Invoice quantity is lower than the ordered quantity.
6. Invoice contains an unexpected line item.
7. Invoice references an incorrect PO number.
8. Vendor names differ.
9. Invoice contains a tax discrepancy.
10. Invoice contains a discount discrepancy.
11. Required fields are missing.
12. A line item cannot be matched confidently.
13. A PDF is unreadable.
14. Invoice total does not match the calculated expected total.

---

## 14. Definition of Done

The MVP is complete when:

- A user can upload one PO and one invoice.
- The system extracts structured data from both documents.
- The extracted data passes validation.
- The system matches corresponding line items.
- The matching engine identifies discrepancies accurately.
- The system generates a readable matching report.
- The workflow is orchestrated using LangGraph.
- Streamlit displays processing status and results.
- Errors are handled without crashing the application.
- The required test scenarios pass.

---

## 15. Development Constraints

- Target completion time: 3–4 days.
- Focus on learning LangGraph through implementation.
- Avoid unnecessary architectural complexity.
- Do not introduce a database in the initial version.
- Do not introduce RAG in this version.
- Use deterministic logic for financial comparisons.
- Keep the application modular and easy to extend.

---

## 16. Future Enhancements

The following features may be considered after the MVP:

- Three-way matching using Goods Receipt Notes.
- OCR support for scanned PDFs.
- Multiple invoices matched against a single PO.
- Manual correction of extracted fields.
- Persistent storage and matching history.
- RAG-based retrieval of company invoice policies.
- Integration with ERP systems.
- Export matching reports to PDF or Excel.