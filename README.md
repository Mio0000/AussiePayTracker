# AussiePayTracker

Analyse Australian payslips (PDF or image) and extract key figures — gross pay, tax, super, net pay, shift breakdown, and YTD totals.

## Supported payroll formats

| Payroll system | Notes |
|---|---|
| **Silk Hospitality** (Lyf Hotel) | Fully tested |
| **Dayforce** (IHG / InterContinental) | Fully tested |
| **MYOB / Xero / KeyPay** | Generic label matching |
| Other AU payslips | Best-effort via common label patterns |

## Supported file types

PDF, PNG, JPG, JPEG, WEBP, TIFF, BMP

Images are processed via Tesseract OCR. PDFs are parsed directly with pdfplumber.

## Setup

```bash
bash setup.sh
```

This creates a `.venv` virtual environment and installs all dependencies.
Tesseract must be installed separately for image support:

```bash
brew install tesseract        # macOS
sudo apt install tesseract-ocr  # Ubuntu/Debian
```

## Usage

### Web UI (recommended)

```bash
source .venv/bin/activate
python app.py
```

Opens `http://localhost:8080` in Chrome automatically.
Drop or select a payslip file, then click **Analyse**.

### Command line

```bash
source .venv/bin/activate
python parse_payslip.py payslip.pdf
```

## What gets extracted

- Employer & employee name / ID
- Base hourly rate
- Pay period (start – end) and pay date
- **Shift breakdown** — date, description, hours, rate, amount (penalty shifts highlighted)
- **Pay summary** — Gross Pay, Tax Withheld, Superannuation, Net Pay
- YTD (Year to Date) figures for all summary items
- Annual leave balance
