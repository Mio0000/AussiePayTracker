"""
AussiePayTracker - Web UI
"""

from pathlib import Path
from flask import Flask, render_template, request, jsonify
from parse_payslip import extract_text_from_pdf, parse_payslip
import tempfile
import os
import pytesseract
from PIL import Image

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB

ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.tiff', '.tif', '.bmp'}


def extract_text_from_image(path: str) -> str:
    img = Image.open(path)
    # グレースケール変換でOCR精度向上
    img = img.convert('L')
    return pytesseract.image_to_string(img, lang='eng')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400

    file = request.files['file']
    suffix = Path(file.filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'Unsupported file type: {suffix}'}), 400

    # 一時ファイルに保存して解析
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        file.save(tmp.name)
        try:
            if suffix == '.pdf':
                text = extract_text_from_pdf(tmp.name)
            else:
                text = extract_text_from_image(tmp.name)
            data = parse_payslip(text)
        finally:
            os.unlink(tmp.name)

    shifts = [
        {
            'date':   s.date,
            'label':  s.label,
            'hours':  s.hours,
            'rate':   s.rate,
            'amount': s.amount,
            'type':   s.type,
        }
        for s in data.shifts
    ]

    return jsonify({
        'employer':          data.employer,
        'employee_name':     data.employee_name,
        'employee_id':       data.employee_id,
        'pay_period_start':  data.pay_period_start,
        'pay_period_end':    data.pay_period_end,
        'pay_date':          data.pay_date,
        'shifts':            shifts,
        'gross_pay':         data.gross_pay,
        'gross_pay_ytd':     data.gross_pay_ytd,
        'tax_withheld':      data.tax_withheld,
        'tax_ytd':           data.tax_ytd,
        'superannuation':    data.superannuation,
        'super_ytd':         data.super_ytd,
        'net_pay':           data.net_pay,
        'net_pay_ytd':       data.net_pay_ytd,
        'annual_leave_hours': data.annual_leave_hours,
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', debug=False, port=port)
