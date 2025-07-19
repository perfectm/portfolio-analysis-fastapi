# Quick Start Guide

## Prerequisites

- Python 3.8 or higher
- pip package manager

## Installation Steps

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/portfolio-analysis-fastapi.git
cd portfolio-analysis-fastapi
```

2. **Create virtual environment (recommended)**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Run the application**

```bash
uvicorn app:app --reload
```

5. **Access the application**
   Open your browser and go to: `http://localhost:8000`

## CSV File Requirements

Your CSV files should have:

- A date column (Date Opened, Date, Trade Date, etc.)
- A P/L column (P/L, PnL, Profit/Loss, etc.)

## Example Usage

1. **Single Portfolio**: Upload one CSV file for individual strategy analysis
2. **Multiple Portfolios**: Upload multiple CSV files for comparative analysis
3. **Blended Analysis**: Automatic combination of multiple strategies with correlation analysis

## Troubleshooting

- Ensure all dependencies are installed correctly
- Check that your CSV files have the required columns
- Verify Python version compatibility (3.8+)
