# Day 2: Multi-File Data Processing Pipeline

## Project Overview

This project processes daily supermarket transaction CSV files for Soko Fresh Supermarkets. The pipeline discovers files automatically, checks the data, separates valid transactions from rejected records, and generates a processing summary.

The aim was to build a reusable pipeline that can handle multiple files while keeping track of data-quality issues.

## Project Structure

```text
day2-multi-file-pipeline/
├── pipeline.py
├── data/
│   ├── transactions_2026-10-01.csv
│   ├── transactions_2026-10-02.csv
│   └── transactions_2026-10-03.csv
├── output/
│   ├── consolidated_transactions.csv
│   ├── rejected_transactions.csv
│   └── summary.txt
├── requirements.txt
└── README.md
```

## What the Pipeline Does

1. Discovers transaction files matching `transactions_*.csv`.
2. Reads CSV records into Python dictionaries.
3. Validates required columns.
4. Checks for missing values, invalid quantities and prices, and duplicate transaction IDs.
5. Cleans valid records, converts numeric fields to integers, and calculates `line_total`.
6. Writes accepted transactions to a consolidated CSV.
7. Writes rejected transactions with their source file, row number, and rejection reasons.
8. Generates a summary containing row counts, rejection counts, and total revenue.

## Data-Quality Decisions

- **Renamed column:** The `qty` column is mapped to `quantity` to accommodate the known change in the third input file.
- **Extra columns:** Additional columns such as `cashier` are allowed; the consolidated output contains only the required columns.
- **Duplicate IDs:** The first occurrence of a transaction ID is retained for consideration, and subsequent occurrences are rejected.
- **Rejected records:** Rejection reasons are recorded so data-quality issues can be investigated rather than silently discarded.

## How to Run

Run the pipeline from the project root:

```powershell
python pipeline.py --input data --output output
```

The input and output folders can also be changed using the `--input` and `--output` arguments.

## Output Files

- `output/consolidated_transactions.csv` — accepted and cleaned transactions.
- `output/rejected_transactions.csv` — rejected transactions and their reasons.
- `output/summary.txt` — processing summary.

## Results of the Current Run

- Files discovered: 3
- Files processed: 3
- Rows read: 43
- Rows accepted: 34
- Rows rejected: 9
- Total revenue: KES 22,775

The accepted and rejected counts reconcile with the total number of input rows: 34 + 9 = 43.

## Skills Practised

Python functions, `pathlib`, CSV processing, dictionaries, lists, sets, comprehensions, validation, exception handling, file writing, and command-line arguments.
