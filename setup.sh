#!/bin/bash
set -e

echo "=== AussiePayTracker - Setup ==="

# Python version check
python3 --version || { echo "Python3 not found. Please install Python 3.8+"; exit 1; }

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate
source .venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip

pip install \
    pdfplumber \
    pypdf2 \
    pandas \
    tabulate \
    python-dateutil \
    rich

echo ""
echo "Setup complete! To activate the environment:"
echo "  source .venv/bin/activate"
