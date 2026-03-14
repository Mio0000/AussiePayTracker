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

## Deploy to Render (free plan)

### 前提条件
- GitHubリポジトリにプッシュ済みであること
- [Render](https://render.com) のアカウントがあること

### 手順

1. **GitHubにプッシュ**
   ```bash
   git add .
   git commit -m "Add Render deployment config"
   git push origin main
   ```

2. **Renderでデプロイ**
   - [Render Dashboard](https://dashboard.render.com) を開く
   - **New → Web Service** を選択
   - GitHubリポジトリを接続して対象リポジトリを選択
   - 以下の設定になっていることを確認（`render.yaml` が自動読み込みされます）:
     - **Build Command**: `apt-get install -y tesseract-ocr tesseract-ocr-eng && pip install -r requirements.txt`
     - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`
   - **Create Web Service** をクリック

3. **デプロイ完了**
   - ビルドログで `Listening at: http://0.0.0.0:XXXX` が表示されれば成功
   - 割り当てられたURLにアクセス（例: `https://aussie-pay-tracker.onrender.com`）

### 注意事項（無料プラン）
- **15分間アクセスがないとスリープ**します。次のアクセス時に30秒〜1分の起動時間がかかります
- ストレージは永続しないため、アップロードファイルはメモリ上で処理されます（現状の実装でも一時ファイルは即削除するため問題なし）
- 月750時間の無料枠あり

## What gets extracted

- Employer & employee name / ID
- Base hourly rate
- Pay period (start – end) and pay date
- **Shift breakdown** — date, description, hours, rate, amount (penalty shifts highlighted)
- **Pay summary** — Gross Pay, Tax Withheld, Superannuation, Net Pay
- YTD (Year to Date) figures for all summary items
- Annual leave balance
