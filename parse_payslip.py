"""
AussiePayTracker - Universal Australian Payslip PDF Parser
Supported formats: Silk Hospitality, Dayforce (IHG/InterContinental), and generic AU payslips
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class ShiftEntry:
    date:   Optional[str]
    hours:  Optional[float]
    rate:   Optional[float]
    amount: float
    type:   str   # "normal" | "penalty" | "allowance"
    label:  str


@dataclass
class PayslipData:
    pay_period_start: Optional[str] = None
    pay_period_end:   Optional[str] = None
    pay_date:         Optional[str] = None

    employee_name: Optional[str] = None
    employee_id:   Optional[str] = None
    employer:      Optional[str] = None
    base_rate:     Optional[float] = None

    gross_pay:      Optional[float] = None
    net_pay:        Optional[float] = None
    tax_withheld:   Optional[float] = None
    superannuation: Optional[float] = None

    gross_pay_ytd: Optional[float] = None
    net_pay_ytd:   Optional[float] = None
    tax_ytd:       Optional[float] = None
    super_ytd:     Optional[float] = None

    shifts: list = field(default_factory=list)
    annual_leave_hours: Optional[float] = None

    raw_text: str = ""


# ── Helpers ───────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text


def parse_number(s: str) -> Optional[float]:
    """Parse amount string to float. Handles trailing minus (e.g. '130.00-' → -130.0)."""
    s = s.strip().replace(',', '').replace('$', '')
    neg = s.endswith('-')
    s   = s.strip('-')
    try:
        val = float(s)
        return -val if neg else val
    except ValueError:
        return None


def normalize_date(d: str) -> str:
    """Expand 2-digit year to 4-digit (e.g. '12/11/25' → '12/11/2025')."""
    parts = re.split(r'[/\-]', d)
    if len(parts) == 3 and len(parts[2]) == 2:
        y = int(parts[2])
        parts[2] = str(2000 + y if y <= 50 else 1900 + y)
    return '/'.join(parts)


def amounts_on_line(line: str) -> list:
    """Return all numeric amounts found on a single line (handles trailing minus)."""
    raw = re.findall(r'\$?([\d,]+\.\d{2}-?)', line)
    return [parse_number(v) for v in raw if parse_number(v) is not None]


def find_line(text: str, label_patterns: list, flags=re.IGNORECASE) -> Optional[str]:
    """Return the first full line matching a label pattern that also contains an amount."""
    for pat in label_patterns:
        for m in re.finditer(pat + r'[^\n]*', text, flags | re.MULTILINE):
            line = m.group(0)
            if amounts_on_line(line):
                return line
    return None


def first_amount(text: str, label_patterns: list) -> Optional[float]:
    """Find the first dollar amount on the first line matching any label."""
    line = find_line(text, label_patterns)
    if line:
        nums = amounts_on_line(line)
        if nums:
            return nums[0]
    return None


def second_amount(text: str, label_patterns: list) -> Optional[float]:
    """Return the second amount on the matched line (used for YTD in Silk format)."""
    line = find_line(text, label_patterns)
    if line:
        nums = amounts_on_line(line)
        if len(nums) >= 2:
            return nums[1]
    return None


# ── Label sets ────────────────────────────────────────────────────────

GROSS_LABELS = [
    r'^Gross\b',                            # Silk
    r'TAXABLE GROSS EARNINGS',              # Dayforce
    r'Total Gross(?:\s+Earnings)?',         # Generic
    r'Gross (?:Pay|Earnings|Salary|Wages)', # Generic
]

NET_LABELS = [
    r'^NET PAY\b',                          # Silk
    r'TOTAL NET PAY\b',                     # Dayforce
    r'Net (?:Pay|Salary|Earnings|Wages)',   # Generic
    r'Take.?Home Pay',                      # Generic
]

TAX_LABELS = [
    r'^Tax\b',                              # Silk
    r'TOTAL TAX DEDUCTED',                  # Dayforce
    r'Tax Withheld',                        # Generic
    r'PAYG(?:\s+Withholding)?',             # Generic
    r'Income Tax',                          # Generic
]

SUPER_LABELS = [
    r'SGC Employer',                        # Silk
    r'ER Super\b',                          # Dayforce
    r'Employer Super(?:annuation)?',        # Generic
    r'Super(?:annuation)?\s+Contribution',  # Generic
]

PERIOD_LABELS = [
    r'Period\s+(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})',
    r'Period of Payment\s+(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})',
    r'Pay Period[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})',
    r'Period Ending[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
]

PAY_DATE_LABELS = [
    r'Pay Date\s+(\d{1,2}/\d{1,2}/\d{2,4})',
    r'Paid on Date\s+(\d{1,2}/\d{1,2}/\d{2,4})',
    r'(?:Payment Date|Date of Payment|Date Paid)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})',
]


# ── Main parser ───────────────────────────────────────────────────────

def parse_payslip(text: str) -> PayslipData:
    data = PayslipData(raw_text=text)
    lines = [l.rstrip() for l in text.split('\n')]

    # ── Pay period ────────────────────────────────────────────────────
    for pat in PERIOD_LABELS:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            data.pay_period_start = normalize_date(m.group(1))
            if m.lastindex >= 2:
                data.pay_period_end = normalize_date(m.group(2))
            break

    # ── Pay date ──────────────────────────────────────────────────────
    for pat in PAY_DATE_LABELS:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            data.pay_date = normalize_date(m.group(1))
            break

    # ── Employee / Employer ───────────────────────────────────────────
    # Silk: "Employee FL38505 Fujisaki, Mio Employer Silk Hospitality Pty Ltd"
    m = re.search(r'Employee\s+(\S+)\s+(.+?)\s+Employer\s+(.+)', text)
    if m:
        data.employee_id   = m.group(1)
        data.employee_name = m.group(2).strip()
        data.employer      = m.group(3).strip()

    # Dayforce: "Payslip for Miss Mio Fujisaki , ID Number 135518"
    if not data.employee_name:
        m = re.search(
            r'Payslip for (?:Miss|Mr|Mrs|Ms|Dr\.?)?\s*(.+?)\s*,\s*ID Number\s+(\S+)',
            text, re.IGNORECASE
        )
        if m:
            data.employee_name = m.group(1).strip()
            data.employee_id   = m.group(2).strip()

    # Dayforce: "Company 72870 InterContinental Hotel Melbourne"
    if not data.employer:
        m = re.search(r'Company\s+\d+\s+(.+)', text)
        if m:
            data.employer = m.group(1).strip()

    # Generic: "Name M Fujisaki"
    if not data.employee_name:
        m = re.search(r'^Name\s+([A-Z].+)', text, re.MULTILINE)
        if m:
            data.employee_name = m.group(1).strip()

    # ── Base rate ─────────────────────────────────────────────────────
    m = re.search(r'Base Rate\s+\$?([\d,]+\.\d+)', text, re.IGNORECASE)
    if m:
        data.base_rate = parse_number(m.group(1))

    # ── Financial totals (current period) ────────────────────────────
    data.gross_pay = first_amount(text, GROSS_LABELS)
    data.net_pay   = first_amount(text, NET_LABELS)

    tax_raw = first_amount(text, TAX_LABELS)
    if tax_raw is not None:
        data.tax_withheld = abs(tax_raw)

    data.superannuation = first_amount(text, SUPER_LABELS)

    # ── YTD (Year to Date) ────────────────────────────────────────────
    # Silk: second number on the same summary line
    data.gross_pay_ytd = second_amount(text, [r'^Gross\b'])
    data.net_pay_ytd   = second_amount(text, [r'^NET PAY\b'])
    tax_ytd_raw        = second_amount(text, [r'^Tax\b'])
    if tax_ytd_raw is not None:
        data.tax_ytd = abs(tax_ytd_raw)

    # Silk: Super YTD is the 3rd amount on the SGC line
    m = re.search(r'SGC Employer\b[^\n]*', text, re.IGNORECASE)
    if m:
        nums = amounts_on_line(m.group(0))
        if len(nums) >= 3:
            data.super_ytd = nums[2]

    # Dayforce: dedicated "YTD Details" section
    # "Taxable Gross $866.98" / "Tax $130.00" / "Net $736.98"
    ytd_m = re.search(r'YTD Details\n(.+?)(?:\n\n|\Z)', text, re.IGNORECASE | re.DOTALL)
    if ytd_m:
        ytd_block = ytd_m.group(1)
        if data.gross_pay_ytd is None:
            data.gross_pay_ytd = first_amount(ytd_block, [r'Taxable Gross\b', r'Gross\b'])
        if data.net_pay_ytd is None:
            data.net_pay_ytd = first_amount(ytd_block, [r'\bNet\b'])
        if data.tax_ytd is None:
            v = first_amount(ytd_block, [r'\bTax\b'])
            if v is not None:
                data.tax_ytd = abs(v)

    # ── Leave balances ────────────────────────────────────────────────
    m = re.search(r'Annual Leave\s+([\d.]+)', text, re.IGNORECASE)
    if m:
        data.annual_leave_hours = float(m.group(1))
    if not data.annual_leave_hours:
        m = re.search(r'^Annual\s+([\d.]+)\s+Hours', text, re.IGNORECASE | re.MULTILINE)
        if m:
            data.annual_leave_hours = float(m.group(1))

    # ── Shift / earnings table ────────────────────────────────────────
    data.shifts = _parse_shifts(lines)

    return data


# ── Shift parser (state machine) ──────────────────────────────────────

PENALTY_RE = re.compile(
    r'(saturday|sunday|public.?holiday|overtime|150%|200%|125%|penalty|sun\b|sat\b)',
    re.IGNORECASE
)

# Silk: "Normal Hours (Normal) 04/12/2025 6.25 Hrs 25.8500 161.56"
SILK_SHIFT = re.compile(
    r'^(.+?)\s+(\d{2}/\d{2}/\d{4})\s+([\d.]+)\s+Hrs\s+([\d.]+)\s+([\d.]+)',
    re.IGNORECASE
)

# Dayforce table header
DAYFORCE_HDR = re.compile(r'Description\s+Date\s+Hours', re.IGNORECASE)

# Dayforce wage line: "M4 SUN 150%  7.50  $37.43  $280.73"
DAYFORCE_WAGE = re.compile(
    r'^(\S.+?)\s+([\d.]+)\s+\$([\d.]+)\s+\$([\d,]+\.\d{2})'
)
# Dayforce allowance line: "AL PEN 7PM-MIDN  $24.87"
DAYFORCE_ALLOW = re.compile(
    r'^(\S[^\n]*?)\s+\$([\d,]+\.\d{2})\s*$'
)
# Lines to skip inside Dayforce table
DAYFORCE_SKIP = re.compile(
    r'^(BEFORE TAX|TAXABLE GROSS|TAX DEDUCT|TOTAL|Sub Total|BENEFIT|'
    r'NET PAY|Description|AFTER TAX|NOTES|Payroll)',
    re.IGNORECASE
)


def _parse_shifts(lines: list) -> list:
    shifts = []
    in_dayforce_table = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Silk shift line
        m = SILK_SHIFT.match(stripped)
        if m:
            label = m.group(1).strip()
            shifts.append(ShiftEntry(
                date=m.group(2),
                hours=float(m.group(3)),
                rate=float(m.group(4)),
                amount=float(m.group(5)),
                type="penalty" if PENALTY_RE.search(label) else "normal",
                label=label,
            ))
            continue

        # Enter Dayforce earnings table
        if DAYFORCE_HDR.search(stripped):
            in_dayforce_table = True
            continue

        if in_dayforce_table:
            if re.match(r'^(TAX DEDUCT|TOTAL NET|BENEFIT|NOTES|Net Pay Distribution)', stripped, re.IGNORECASE):
                in_dayforce_table = False
                continue
            if DAYFORCE_SKIP.match(stripped):
                continue

            # Wage line (hours + rate)
            m = DAYFORCE_WAGE.match(stripped)
            if m:
                label = m.group(1).strip()
                shifts.append(ShiftEntry(
                    date=None,
                    hours=float(m.group(2)),
                    rate=float(m.group(3)),
                    amount=float(m.group(4).replace(',', '')),
                    type="penalty" if PENALTY_RE.search(label) else "normal",
                    label=label,
                ))
                continue

            # Allowance line (amount only)
            m = DAYFORCE_ALLOW.match(stripped)
            if m:
                label = m.group(1).strip()
                if not re.match(r'(Sub Total|Total)', label, re.IGNORECASE):
                    shifts.append(ShiftEntry(
                        date=None,
                        hours=None,
                        rate=None,
                        amount=float(m.group(2).replace(',', '')),
                        type="allowance",
                        label=label,
                    ))

    return shifts


# ── Display ───────────────────────────────────────────────────────────

def display_payslip(data: PayslipData):
    console.print()
    console.print(f"[bold cyan]Employer:[/bold cyan]   {data.employer or '—'}")
    console.print(f"[bold cyan]Employee:[/bold cyan]   {data.employee_name or '—'}  ({data.employee_id or '—'})")
    if data.base_rate:
        console.print(f"[bold cyan]Base Rate:[/bold cyan]  ${data.base_rate:.4f}")
    console.print(f"[bold cyan]Period:[/bold cyan]     {data.pay_period_start or '—'} – {data.pay_period_end or '—'}")
    console.print(f"[bold cyan]Pay Date:[/bold cyan]   {data.pay_date or '—'}")
    console.print()

    if data.shifts:
        t = Table(title="Shift Breakdown", header_style="bold")
        t.add_column("Date")
        t.add_column("Description")
        t.add_column("Hours",  justify="right")
        t.add_column("Rate",   justify="right")
        t.add_column("Amount", justify="right")

        total_hours = 0.0
        total_amount = 0.0
        for s in data.shifts:
            style = "yellow" if s.type == "penalty" else ("dim" if s.type == "allowance" else "")
            t.add_row(
                s.date or "—", s.label,
                f"{s.hours:.2f} h" if s.hours is not None else "—",
                f"${s.rate:.4f}"  if s.rate  is not None else "—",
                f"${s.amount:.2f}",
                style=style,
            )
            if s.hours:
                total_hours += s.hours
            total_amount += s.amount

        t.add_section()
        t.add_row(
            "Total", "",
            f"{total_hours:.2f} h" if total_hours else "—",
            "", f"${total_amount:.2f}",
            style="bold",
        )
        console.print(t)
        console.print()

    def fmt(v):     return f"${v:,.2f}"  if v is not None else "—"
    def fmt_neg(v): return f"-${v:,.2f}" if v is not None else "—"

    s = Table(title="Pay Summary", header_style="bold")
    s.add_column("Item",     style="bold")
    s.add_column("This Pay", justify="right")
    s.add_column("YTD",      justify="right")
    s.add_row("Gross Pay",       fmt(data.gross_pay),       fmt(data.gross_pay_ytd))
    s.add_row("Tax Withheld",    fmt_neg(data.tax_withheld), fmt_neg(data.tax_ytd))
    s.add_row("Superannuation",  fmt(data.superannuation),  fmt(data.super_ytd))
    s.add_row("Net Pay",         fmt(data.net_pay),         fmt(data.net_pay_ytd))
    if data.annual_leave_hours is not None:
        s.add_row("Annual Leave Balance", f"{data.annual_leave_hours:.2f} h", "")
    console.print(s)
    console.print()


def process_pdf(pdf_path: str) -> PayslipData:
    path = Path(pdf_path)
    if not path.exists():
        console.print(f"[red]Error: file not found: {pdf_path}[/red]")
        sys.exit(1)
    console.print(f"[green]Parsing:[/green] {path.name}")
    text = extract_text_from_pdf(pdf_path)
    data = parse_payslip(text)
    display_payslip(data)
    return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[yellow]Usage: python parse_payslip.py <payslip.pdf>[/yellow]")
        sys.exit(0)
    process_pdf(sys.argv[1])
