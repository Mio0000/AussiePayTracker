"""
Unit + integration tests for parse_payslip.py
Run: pytest tests/
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parse_payslip import (
    parse_number, normalize_date, amounts_on_line,
    parse_payslip, extract_text_from_pdf,
)

# ── Helper function tests ──────────────────────────────────────────────────────

class TestParseNumber:
    def test_basic_float(self):
        assert parse_number('25.50') == 25.5

    def test_trailing_minus(self):
        assert parse_number('130.00-') == -130.0

    def test_with_dollar_sign(self):
        assert parse_number('$1,234.56') == 1234.56

    def test_with_commas(self):
        assert parse_number('1,234.56') == 1234.56

    def test_zero(self):
        assert parse_number('0.00') == 0.0

    def test_invalid_returns_none(self):
        assert parse_number('abc') is None

    def test_empty_returns_none(self):
        assert parse_number('') is None


class TestNormalizeDate:
    def test_two_digit_year_2000s(self):
        assert normalize_date('12/11/25') == '12/11/2025'

    def test_four_digit_year_unchanged(self):
        assert normalize_date('12/11/2025') == '12/11/2025'

    def test_century_boundary(self):
        # year 51 → 1951, year 50 → 2050
        assert normalize_date('01/01/51') == '01/01/1951'
        assert normalize_date('01/01/50') == '01/01/2050'

    def test_hyphen_separator(self):
        assert normalize_date('04-12-25') == '04/12/2025'


class TestAmountsOnLine:
    def test_single_amount(self):
        assert amounts_on_line('Gross 1,100.25') == [1100.25]

    def test_multiple_amounts(self):
        assert amounts_on_line('Gross 1,100.25 1,746.50') == [1100.25, 1746.50]

    def test_trailing_minus(self):
        assert amounts_on_line('Tax 165.00-') == [-165.0]

    def test_no_amounts(self):
        assert amounts_on_line('No amounts here') == []

    def test_dollar_prefix(self):
        assert amounts_on_line('Net $935.25') == [935.25]


# ── Sample text fixtures ───────────────────────────────────────────────────────

SILK_SAMPLE = """\
Location Lyf Hotel Melbourne Pay Advice
Employee FL38505 Fujisaki, Mio Employer Silk Hospitality Pty Ltd
Address 11 Darriwill Cl Delahey
Period 01/12/2025 - 14/12/2025 Pay Date 18/12/2025
Details Leave / Dates Hours Rate / Perc Amount
Normal Hours (Normal) 04/12/2025 6.25 Hrs 25.8500 161.56
Normal Hours (Normal) 05/12/2025 6.00 Hrs 25.8500 155.10
Normal Hours (Normal) 09/12/2025 7.00 Hrs 25.8500 180.95
Saturday Rate FT/PT 06/12/2025 5.25 Hrs 32.3125 169.64 B*
Superannuation This Pay Period to Date Year to Date
Australian Super, 12% SGC Employer 132.03 132.03 209.58
Item This Pay Year to Date
Gross 1,100.25 1,746.50
Tax -165.00 -359.00
NET PAY 935.25 1,387.50
Annual Leave 5.10
"""

SALARIED_SAMPLE = """\
SUMMIT TECH SOLUTIONS PTY LTD
PAY ADVICE
Employee Name: John Smith
Employee ID: EMP001
Employer: Summit Tech Solutions Pty Ltd
Pay Period: 01/03/2026 - 31/03/2026
Pay Date: 31/03/2026

EARNINGS
Monthly Salary                     5,000.00
Car Allowance                        200.00
Mobile Allowance                      50.00
Total Earnings                     5,250.00

TAX
Income Tax                         1,125.00

NET PAY                            4,125.00

SUPERANNUATION
Employer Super (12%)                 630.00
"""

DAYFORCE_SAMPLE = """\
Payslip for Miss Jane Doe , ID Number 999001
Company 12345 InterContinental Hotel Sydney
Period 01/11/2025 - 14/11/2025 Pay Date 20/11/2025
Description Date Hours
M4 Regular  7.50 $28.50 $213.75
M4 SUN 150%  6.00 $42.75 $256.50
AL PEN 7PM-MIDN  $24.87
TAXABLE GROSS EARNINGS 495.12
TAX DEDUCTED 74.27
TOTAL NET PAY 420.85
ER Super 54.46
YTD Details
Taxable Gross $4,500.00
Tax $680.00
Net $3,820.00
"""


# ── Silk format ────────────────────────────────────────────────────────────────

class TestSilkFormat:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.d = parse_payslip(SILK_SAMPLE)

    def test_employee_name(self):
        assert self.d.employee_name == 'Fujisaki, Mio'

    def test_employee_id(self):
        assert self.d.employee_id == 'FL38505'

    def test_employer(self):
        assert self.d.employer == 'Silk Hospitality Pty Ltd'

    def test_pay_period(self):
        assert self.d.pay_period_start == '01/12/2025'
        assert self.d.pay_period_end   == '14/12/2025'

    def test_pay_date(self):
        assert self.d.pay_date == '18/12/2025'

    def test_gross(self):
        assert self.d.gross_pay == 1100.25

    def test_gross_ytd(self):
        assert self.d.gross_pay_ytd == 1746.50

    def test_net(self):
        assert self.d.net_pay == 935.25

    def test_net_ytd(self):
        assert self.d.net_pay_ytd == 1387.50

    def test_tax(self):
        assert self.d.tax_withheld == 165.0

    def test_tax_ytd(self):
        assert self.d.tax_ytd == 359.0

    def test_super(self):
        assert self.d.superannuation == 132.03

    def test_super_ytd(self):
        assert self.d.super_ytd == 209.58

    def test_annual_leave(self):
        assert self.d.annual_leave_hours == 5.10

    def test_shift_count(self):
        assert len(self.d.shifts) == 4

    def test_normal_shift(self):
        s = self.d.shifts[0]
        assert s.date   == '04/12/2025'
        assert s.hours  == 6.25
        assert s.rate   == 25.85
        assert s.amount == 161.56
        assert s.type   == 'normal'

    def test_penalty_shift(self):
        s = self.d.shifts[3]
        assert s.type == 'penalty'
        assert 'Saturday' in s.label

    def test_no_ytd_rows_in_shifts(self):
        for s in self.d.shifts:
            assert 'ytd' not in s.label.lower()
            assert 'gross' not in s.label.lower()


# ── Salaried format ────────────────────────────────────────────────────────────

class TestSalariedFormat:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.d = parse_payslip(SALARIED_SAMPLE)

    def test_employee_name(self):
        assert self.d.employee_name == 'John Smith'

    def test_employer(self):
        assert self.d.employer == 'Summit Tech Solutions Pty Ltd'

    def test_pay_period(self):
        assert self.d.pay_period_start == '01/03/2026'
        assert self.d.pay_period_end   == '31/03/2026'

    def test_pay_date(self):
        assert self.d.pay_date == '31/03/2026'

    def test_net(self):
        assert self.d.net_pay == 4125.0

    def test_earnings_parsed(self):
        labels = [s.label for s in self.d.shifts]
        assert 'Monthly Salary' in labels
        assert 'Car Allowance'  in labels

    def test_no_hours_or_rate(self):
        for s in self.d.shifts:
            assert s.hours is None
            assert s.rate  is None
            assert s.date  is None

    def test_total_row_excluded(self):
        labels = [s.label.lower() for s in self.d.shifts]
        assert not any('total' in l for l in labels)

    def test_no_tax_or_super_in_shifts(self):
        labels = [s.label.lower() for s in self.d.shifts]
        assert not any('income tax' in l for l in labels)
        assert not any('super' in l for l in labels)


# ── Dayforce format ────────────────────────────────────────────────────────────

class TestDayforceFormat:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.d = parse_payslip(DAYFORCE_SAMPLE)

    def test_employee_name(self):
        assert self.d.employee_name == 'Jane Doe'

    def test_employer(self):
        assert 'InterContinental' in self.d.employer

    def test_gross(self):
        assert self.d.gross_pay == 495.12

    def test_net(self):
        assert self.d.net_pay == 420.85

    def test_tax(self):
        assert self.d.tax_withheld == 74.27

    def test_super(self):
        assert self.d.superannuation == 54.46

    def test_ytd_gross(self):
        assert self.d.gross_pay_ytd == 4500.0

    def test_ytd_tax(self):
        assert self.d.tax_ytd == 680.0

    def test_ytd_net(self):
        assert self.d.net_pay_ytd == 3820.0

    def test_wage_shift_parsed(self):
        wage_shifts = [s for s in self.d.shifts if s.hours is not None]
        assert len(wage_shifts) >= 1

    def test_penalty_shift(self):
        assert any(s.type == 'penalty' for s in self.d.shifts)

    def test_allowance_shift(self):
        assert any(s.type == 'allowance' for s in self.d.shifts)

    def test_no_ytd_in_shifts(self):
        for s in self.d.shifts:
            assert 'ytd' not in s.label.lower()
            assert 'taxable gross' not in s.label.lower()
            assert 'total net' not in s.label.lower()


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_string(self):
        d = parse_payslip('')
        assert d.employee_name is None
        assert d.employer      is None
        assert d.gross_pay     is None
        assert d.net_pay       is None
        assert d.shifts        == []

    def test_whitespace_only(self):
        d = parse_payslip('   \n\n   ')
        assert d.shifts == []

    def test_no_shifts_section(self):
        d = parse_payslip('Gross 1000.00\nNET PAY 800.00')
        assert d.gross_pay == 1000.0
        assert d.net_pay   == 800.0
        assert d.shifts    == []


# ── Integration test (real PDF) ───────────────────────────────────────────────

_PDF_PATH = os.path.join(os.path.dirname(__file__), '..', 'payslip_test.pdf')

@pytest.mark.skipif(not os.path.exists(_PDF_PATH), reason='payslip_test.pdf not found')
class TestSilkPDFIntegration:
    @pytest.fixture(autouse=True)
    def setup(self):
        text    = extract_text_from_pdf(_PDF_PATH)
        self.d  = parse_payslip(text)

    def test_employee_name(self):
        assert self.d.employee_name == 'Fujisaki, Mio'

    def test_employer(self):
        assert self.d.employer == 'Silk Hospitality Pty Ltd'

    def test_pay_date(self):
        assert self.d.pay_date == '18/12/2025'

    def test_gross(self):
        assert self.d.gross_pay == 1100.25

    def test_net(self):
        assert self.d.net_pay == 935.25

    def test_tax(self):
        assert self.d.tax_withheld == 165.0

    def test_super(self):
        assert self.d.superannuation == 132.03

    def test_seven_shifts(self):
        assert len(self.d.shifts) == 7

    def test_no_garbage_in_shifts(self):
        for s in self.d.shifts:
            assert s.amount > 0
            assert s.date is not None
