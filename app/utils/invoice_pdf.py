"""Formatted tax-invoice PDF generation with the HAL logo (100px) letterhead."""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from starlette.responses import StreamingResponse

from app.models.invoice import Invoice
from app.utils.branding import LOGO_PATH, logo_dimensions_pt

LOGO_WIDTH_PX = 100


def build_invoice_pdf(invoice: Invoice) -> bytes:
    """Render a single invoice to PDF bytes with the company letterhead."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("HalTitle", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#1E3A8A"))
    label_style = ParagraphStyle("HalLabel", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#475569"))
    normal_style = styles["Normal"]

    elements = []

    px_to_pt = 0.75
    logo_width, logo_height = logo_dimensions_pt(LOGO_WIDTH_PX * px_to_pt)
    header_table = Table(
        [[Image(LOGO_PATH, width=logo_width, height=logo_height), Paragraph("Hindustan Aeronautics Limited<br/>TAX INVOICE", title_style)]],
        colWidths=[logo_width + 10, None],
    )
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    elements.append(header_table)
    elements.append(Spacer(1, 10))

    meta_data = [
        ["Invoice Number:", invoice.invoice_number, "Invoice Date:", invoice.invoice_date.strftime("%d-%b-%Y")],
        ["Customer Name:", invoice.customer_name, "Contract #:", invoice.contract.contract_number],
        ["GSTIN:", invoice.gstin or "—", "PAN:", invoice.pan or "—"],
    ]
    meta_table = Table(meta_data, colWidths=[85, 190, 85, 130])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 14))

    line_headers = ["#", "Description", "Quantity", "Unit Rate (₹)", "Amount (₹)"]
    line_rows = [line_headers]
    for idx, item in enumerate(invoice.invoiced_line_items, start=1):
        line_rows.append(
            [idx, item.description, f"{item.quantity:.2f}", f"{item.unit_rate:,.2f}", f"{item.amount:,.2f}"]
        )
    if len(line_rows) == 1:
        line_rows.append(["1", "As per contract", f"{invoice.quantity:.2f}", f"{invoice.unit_rate:,.2f}", f"{invoice.line_total:,.2f}"])

    items_table = Table(line_rows, colWidths=[25, 220, 70, 90, 90], repeatRows=1)
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
            ]
        )
    )
    elements.append(items_table)
    elements.append(Spacer(1, 10))

    totals_data = [
        ["Line Total", f"Rs. {invoice.line_total:,.2f}"],
        [f"GST @ {invoice.gst_percentage}%", f"Rs. {invoice.gst_amount:,.2f}"],
        ["Grand Total", f"Rs. {invoice.grand_total:,.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[400, 95], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("LINEABOVE", (0, 2), (-1, 2), 0.75, colors.black),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    elements.append(totals_table)
    elements.append(Spacer(1, 14))

    elements.append(Paragraph("Amount in Words:", label_style))
    elements.append(Paragraph(f"<b>{invoice.amount_in_words}</b>", normal_style))
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("This is a system-generated invoice from the Offline ERP HAL system.", label_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def invoice_pdf_response(invoice: Invoice) -> StreamingResponse:
    pdf_bytes = build_invoice_pdf(invoice)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'},
    )
