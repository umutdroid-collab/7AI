"""Turkish e-Fatura / e-Arşiv PDF metin çıkarımı.

PDF'ler farklı e-fatura entegratörlerinden (Logo, Mikro, Paraşüt, Nes, vb.)
gelebildiği için tek bir sabit şablon yok. Bu yüzden etiket tabanlı regex
eşleştirmesi kullanılır: "Fatura No", "Fatura Tarihi", "Vade Tarihi",
"Ödenecek Tutar" gibi yaygın etiketlerin yanındaki değeri okuruz.
Hiçbir alan bulunamazsa fatura NEEDS_REVIEW durumunda düşer ve çalışan
uygulama üzerinden elle düzeltebilir.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime

import pdfplumber

DATE_RE = r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})"
AMOUNT_RE = r"([\d.,]+)\s*(TRY|TL|USD|EUR|₺|\$|€)?"

INVOICE_NO_LABELS = [
    r"Fatura\s*No\s*[:\-]?\s*([A-Z0-9]{10,20})",
    r"Fatura\s*Numaras[ıi]\s*[:\-]?\s*([A-Z0-9]{10,20})",
    r"ETTN\s*[:\-]?\s*([A-Za-z0-9\-]{20,40})",
]

INVOICE_DATE_LABELS = [
    rf"Fatura\s*Tarihi\s*[:\-]?\s*{DATE_RE}",
    rf"D[uü]zenleme\s*Tarihi\s*[:\-]?\s*{DATE_RE}",
]

DUE_DATE_LABELS = [
    rf"Vade\s*Tarihi\s*[:\-]?\s*{DATE_RE}",
    rf"Son\s*[ÖO]deme\s*Tarihi\s*[:\-]?\s*{DATE_RE}",
    rf"[ÖO]deme\s*Vadesi\s*[:\-]?\s*{DATE_RE}",
]

AMOUNT_LABELS = [
    rf"[ÖO]denecek\s*Tutar\s*[:\-]?\s*{AMOUNT_RE}",
    rf"Vergiler\s*Dahil\s*Toplam\s*Tutar\s*[:\-]?\s*{AMOUNT_RE}",
    rf"Genel\s*Toplam\s*[:\-]?\s*{AMOUNT_RE}",
    rf"[ÖO]denecek\s*Tutar\s*\(?[Yy]aln[ıi]z\)?\s*[:\-]?\s*{AMOUNT_RE}",
]

COUNTERPARTY_LABELS = [
    r"Say[ıi]n\s*[:\-]?\s*([A-ZÇĞİÖŞÜa-zçğıöşü0-9 .,&\-]{4,120})",
    r"Al[ıi]c[ıi]\s*[:\-]?\s*([A-ZÇĞİÖŞÜa-zçğıöşü0-9 .,&\-]{4,120})",
    r"[ÜU]nvan[ıi]?\s*[:\-]?\s*([A-ZÇĞİÖŞÜa-zçğıöşü0-9 .,&\-]{4,120})",
]

CURRENCY_MAP = {"₺": "TRY", "TL": "TRY", "$": "USD", "€": "EUR"}


@dataclass
class ParsedInvoice:
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    amount: float | None = None
    currency: str = "TRY"
    counterparty: str | None = None
    raw_text_excerpt: str = ""
    confidence: float = 0.0
    fields_found: list[str] = field(default_factory=list)


def _parse_tr_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%y", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_tr_amount(raw: str) -> float | None:
    raw = raw.strip()
    try:
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            raw = raw.replace(",", ".")
        return round(float(raw), 2)
    except ValueError:
        return None


def _first_match(patterns: list[str], text: str) -> tuple[str | None, str | None]:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            groups = m.groups()
            return groups[0], (groups[1] if len(groups) > 1 else None)
    return None, None


def extract_text(pdf_path: str) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:5]:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts)


def parse_invoice_pdf(pdf_path: str) -> ParsedInvoice:
    text = extract_text(pdf_path)
    result = ParsedInvoice(raw_text_excerpt=text[:2000])

    inv_no, _ = _first_match(INVOICE_NO_LABELS, text)
    if inv_no:
        result.invoice_number = inv_no.strip()
        result.fields_found.append("invoice_number")

    inv_date_raw, _ = _first_match(INVOICE_DATE_LABELS, text)
    if inv_date_raw:
        parsed = _parse_tr_date(inv_date_raw)
        if parsed:
            result.invoice_date = parsed
            result.fields_found.append("invoice_date")

    due_date_raw, _ = _first_match(DUE_DATE_LABELS, text)
    if due_date_raw:
        parsed = _parse_tr_date(due_date_raw)
        if parsed:
            result.due_date = parsed
            result.fields_found.append("due_date")
    elif result.invoice_date:
        # Vade tarihi belirtilmemişse fatura tarihi vade tarihi olarak kabul edilmez;
        # NEEDS_REVIEW durumuna düşmesi için boş bırakılır.
        pass

    amount_raw, currency_raw = _first_match(AMOUNT_LABELS, text)
    if amount_raw:
        parsed_amount = _parse_tr_amount(amount_raw)
        if parsed_amount is not None:
            result.amount = parsed_amount
            result.fields_found.append("amount")
            if currency_raw:
                result.currency = CURRENCY_MAP.get(currency_raw, currency_raw)

    counterparty, _ = _first_match(COUNTERPARTY_LABELS, text)
    if counterparty:
        result.counterparty = counterparty.strip().rstrip(".,")
        result.fields_found.append("counterparty")

    required = {"invoice_number", "invoice_date", "due_date", "amount"}
    result.confidence = round(len(required & set(result.fields_found)) / len(required), 2)

    return result
