import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FOLDER = BASE_DIR / "Data" / "raw"


def find_date_column(df):
    """Find the date column."""

    possible_names = [
        "date",
        "datetime",
        "time"
    ]

    for column in df.columns:
        if column.lower().strip() in possible_names:
            return column

    return None


def audit_csv(file_path):
    """Audit one CSV dataset."""

    print("\n" + "=" * 70)
    print(f"DATASET: {file_path.name}")
    print("=" * 70)

    try:
        df = pd.read_csv(file_path)
    except Exception as error:
        print(f"Could not read file: {error}")
        return

    print(f"\nRows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    print("\nColumn names:")
    for column in df.columns:
        print(f"  - {column}")

    date_column = find_date_column(df)

    if date_column is None:
        print("\nNo date column found.")
        return

    df[date_column] = pd.to_datetime(
        df[date_column],
        errors="coerce"
    )

    valid_dates = df[date_column].dropna()

    print("\nDATE ANALYSIS")
    print("-" * 70)

    print(f"Date column: {date_column}")
    print(f"Invalid dates: {df[date_column].isna().sum()}")

    if len(valid_dates) == 0:
        print("No valid dates found.")
        return

    print(f"Earliest date: {valid_dates.min().date()}")
    print(f"Latest date:   {valid_dates.max().date()}")

    duplicate_dates = df[date_column].duplicated().sum()

    print(f"Duplicate dates: {duplicate_dates}")

    sorted_dates = valid_dates.sort_values()

    gaps = sorted_dates.diff().dt.days.dropna()

    if len(gaps) > 0:
        print(f"Largest gap: {gaps.max()} days")

        print("\nGap distribution:")
        print(gaps.value_counts().sort_index().to_string())

    print("\nMISSING VALUES")
    print("-" * 70)

    missing = df.isna().sum()

    missing = missing[missing > 0].sort_values(
        ascending=False
    )

    if len(missing) == 0:
        print("No missing values found.")
    else:
        for column, count in missing.items():
            percentage = (count / len(df)) * 100

            print(
                f"{column}: "
                f"{count} missing "
                f"({percentage:.2f}%)"
            )

    print("\nDATA TYPES")
    print("-" * 70)

    print(df.dtypes.to_string())

    print("\nFREIGHT INDEX COLUMNS")
    print("-" * 70)

    index_columns = [
    "BDI",
    "BCI",
    "BPI",
    "BSI",
    "BHSI"
    ]

    for column in index_columns:
        if column in df.columns:

            valid_count = df[column].notna().sum()

            print(
                f"{column}: "
                f"{valid_count}/{len(df)} "
                f"non-missing values"
            )

    print("\nSTATUS COLUMNS")
    print("-" * 70)

    status_columns = [
        column
        for column in df.columns
        if "status" in column.lower()
    ]

    if not status_columns:
        print("No status columns found.")
    else:
        for column in status_columns:

            print(f"\n{column}:")
            print(
                df[column]
                .value_counts(dropna=False)
                .to_string()
            )


def main():

    print("=" * 70)
    print("CARGOCAST DATA AUDIT")
    print("=" * 70)

    if not RAW_FOLDER.exists():
        print(f"\nRaw folder not found:")
        print(RAW_FOLDER)
        return

    csv_files = list(
        RAW_FOLDER.glob("*.csv")
    )

    if not csv_files:
        print("\nNo CSV files found in Data/raw/")
        return

    print(f"\nFound {len(csv_files)} CSV file(s).")

    for file in csv_files:
        audit_csv(file)

    print("\n" + "=" * 70)
    print("AUDIT COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()