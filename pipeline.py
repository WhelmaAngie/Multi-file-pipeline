
import csv
import logging
from pathlib import Path
import argparse
from datetime import datetime


REQUIRED_COLUMNS: set[str] = {
    "transaction_id",
    "date",
    "branch",
    "customer_id",
    "product",
    "quantity",
    "unit_price",
    "payment_method",
}

COLUMN_ALIASES: dict[str, str] = {
    "qty": "quantity",
}


def discover_files(folder: Path, pattern: str = "transactions_*.csv") -> list[Path]:
    """Find matching CSV files and return them in sorted order."""
    files = sorted(folder.glob(pattern))
    return files


def read_transactions(path: Path) -> tuple[list[str], list[dict]]:
    """Read a CSV file and return its header and transaction rows."""
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        header = reader.fieldnames or []
        rows = []

        for line_number, row in enumerate(reader, start=2):
            row["source_file"] = path.name
            row["row_number"] = line_number
            rows.append(row)

    return header, rows


def validate_columns(
    header: list[str],
    required: set[str] = REQUIRED_COLUMNS
) -> set[str]:
    """Return required columns that are missing from the header."""
    normalized_header = {
        COLUMN_ALIASES.get(column.strip(), column.strip())
        for column in header
    }

    missing_columns = required - normalized_header
    return missing_columns


def find_problems(row: dict, seen_ids: set[str]) -> list[str]:
    """Return all validation problems found in a transaction."""
    problems = []

    required_fields = REQUIRED_COLUMNS

    # Check for blank required fields.
    for field in required_fields:
        value = row.get(field, "")

        # Accept the known alias for quantity.
        if field == "quantity" and not value:
            value = row.get("qty", "")

        if value is None or not str(value).strip():
            problems.append(f"Missing value: {field}")

    # Check that quantity and unit price are positive numbers.

    # Check that quantity and unit price are positive numbers.
    for field in ("quantity", "unit_price"):
        value = row.get(field, "")

        if field == "quantity" and not value:
            value = row.get("qty", "")

        # Missing values are already reported above.
        if value is None or not str(value).strip():
            continue

        try:
            number = int(str(value).strip())

            if number <= 0:
                problems.append(
                    f"Invalid number: {field} must be positive"
                )

        except (ValueError, TypeError):
            problems.append(
                f"Invalid number: {field} must be a number"
            )

    # Check for duplicate transaction IDs.
    transaction_id = str(row.get("transaction_id", "")).strip()

    if transaction_id and transaction_id in seen_ids:
        problems.append(f"Duplicate transaction ID: {transaction_id}")

    return problems


def clean_row(row: dict) -> dict:
    """Return a cleaned copy of a valid transaction."""
    cleaned = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in row.items()
    }

    # Standardize the renamed quantity column.
    if "quantity" not in cleaned and "qty" in cleaned:
        cleaned["quantity"] = cleaned["qty"]

    cleaned.pop("qty", None)

    # Convert numeric fields to integers.
    cleaned["quantity"] = int(cleaned["quantity"])
    cleaned["unit_price"] = int(cleaned["unit_price"])

    # Calculate the transaction total.
    cleaned["line_total"] = (
        cleaned["quantity"] * cleaned["unit_price"]
    )

    return cleaned


def write_csv(
    rows: list[dict],
    path: Path,
    fieldnames: list[str]
) -> None:
    """Write dictionaries to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(rows)


def build_summary(stats: dict) -> str:
    """Format the pipeline processing summary."""
    column_issues = stats["column_issues"]

    if column_issues:
        issue_text = "; ".join(
            f"{name}: missing {', '.join(sorted(missing))}"
            for name, missing in column_issues
        )
    else:
        issue_text = "none"

    return (
        "=== Processing summary ===\n"
        f"Files discovered:        {stats['files_discovered']}\n"
        f"Files processed:         {stats['files_processed']}\n"
        f"Files with column issues:{len(column_issues)}"
        f"  ({issue_text})\n"
        f"Rows read:               {stats['rows_read']}\n"
        f"Rows accepted:           {stats['rows_accepted']}\n"
        f"Rows rejected:           {stats['rows_rejected']}\n"
        f"  - missing values:      {stats['missing_values']}\n"
        f"  - invalid numbers:     {stats['invalid_numbers']}\n"
        f"  - duplicate IDs:       {stats['duplicate_ids']}\n"
        f"Total revenue (KES):     {stats['total_revenue']}\n"
        f"Run finished at:         {stats['run_finished_at']}\n"
    )


def run_pipeline(input_dir: Path, output_dir: Path) -> dict:
    """Process all transaction files and write the required outputs."""

    files = discover_files(input_dir)

    accepted = []
    rejected = []
    seen_ids = set()
    all_original_columns = []

    stats = {
        "files_discovered": len(files),
        "files_processed": 0,
        "column_issues": [],
        "rows_read": 0,
        "rows_accepted": 0,
        "rows_rejected": 0,
        "missing_values": 0,
        "invalid_numbers": 0,
        "duplicate_ids": 0,
        "total_revenue": 0,
        "run_finished_at": "",
    }

    for file_path in files:
        try:
            header, rows = read_transactions(file_path)
        except (OSError, csv.Error, UnicodeError) as error:
            logging.error("Could not read %s: %s", file_path.name, error)
            raise RuntimeError(
                f"Could not read input file: {file_path.name}"
            ) from error

        stats["files_processed"] += 1
        stats["rows_read"] += len(rows)

        # Preserve the original column names for rejected records.
        for column in header:
            if column not in all_original_columns:
                all_original_columns.append(column)

        missing = validate_columns(header)

        if missing:
            stats["column_issues"].append(
                (file_path.name, missing)
            )

            # Keep every row accounted for if the file has a bad schema.
            for row in rows:
                transaction_id = str(
                    row.get("transaction_id", "")
                ).strip()

                rejected.append({
                    **row,
                    "transaction_id": transaction_id,
                    "reasons": (
                        "File missing required columns: "
                        + ", ".join(sorted(missing))
                    ),
                })

                if transaction_id:
                    seen_ids.add(transaction_id)

            continue

        for row in rows:
            problems = find_problems(row, seen_ids)

            transaction_id = str(
                row.get("transaction_id", "")
            ).strip()

            # Count IDs across the whole run, including rejected rows.
            if transaction_id:
                seen_ids.add(transaction_id)

            if problems:
                rejected.append({
                    **row,
                    "transaction_id": transaction_id,
                    "reasons": "; ".join(problems),
                })

                if any(reason.startswith("Missing value:")
                       for reason in problems):
                    stats["missing_values"] += 1

                if any(reason.startswith("Invalid number:")
                       for reason in problems):
                    stats["invalid_numbers"] += 1

                if any(reason.startswith("Duplicate transaction ID:")
                       for reason in problems):
                    stats["duplicate_ids"] += 1

                continue

            cleaned = clean_row(row)
            accepted.append(cleaned)
            stats["total_revenue"] += cleaned["line_total"]

    stats["rows_accepted"] = len(accepted)
    stats["rows_rejected"] = len(rejected)
    stats["run_finished_at"] = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    # Consolidated output: use the exact required column order.
    accepted_columns = [
        "transaction_id",
        "date",
        "branch",
        "customer_id",
        "product",
        "quantity",
        "unit_price",
        "line_total",
        "payment_method",
        "payment_ref",
        "source_file",
    ]

    write_csv(
        accepted,
        output_dir / "consolidated_transactions.csv",
        accepted_columns,
    )

    # Rejected output: preserve the original columns as well as reasons.
    reserved_columns = {
        "source_file", "row_number", "transaction_id", "reasons"
    }

    rejected_columns = [
        "source_file",
        "row_number",
        "transaction_id",
        "reasons",
        *[
            column for column in all_original_columns
            if column not in reserved_columns
        ],
    ]

    write_csv(
        rejected,
        output_dir / "rejected_transactions.csv",
        rejected_columns,
    )

    summary = build_summary(stats)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.txt").write_text(
        summary,
        encoding="utf-8",
    )

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process daily supermarket transaction CSV files."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data"),
        help="Folder containing input CSV files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Folder for generated output files.",
    )

    args = parser.parse_args()

    try:
        stats = run_pipeline(args.input, args.output)
        print(build_summary(stats))
    except (OSError, RuntimeError, csv.Error) as error:
        logging.error("Pipeline failed: %s", error)
        raise SystemExit(1)
