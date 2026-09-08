import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FOLDER = BASE_DIR / "Data" / "raw"
PROCESSED_FOLDER = BASE_DIR / "Data" / "processed"


def find_date_column(df):
    """Find a likely date column."""

    for column in df.columns:
        if column.lower().strip() in ["date", "datetime", "time"]:
            return column

    return None


def load_dataset(file_path):
    """Load and standardize one CSV dataset."""

    df = pd.read_csv(file_path)

    # Clean column names
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    date_column = find_date_column(df)

    if date_column is None:
        print(f"No date column in {file_path.name}")
        return None

    # Convert date column
    df[date_column] = pd.to_datetime(
        df[date_column],
        errors="coerce"
    )

    # Remove invalid dates
    df = df.dropna(subset=[date_column])

    # Standardize date column name
    df = df.rename(
        columns={date_column: "date"}
    )

    # Sort by date
    df = df.sort_values("date")

    return df


def main():

    print("=" * 60)
    print("CARGOCAST DATA MERGER")
    print("=" * 60)

    csv_files = list(RAW_FOLDER.glob("*.csv"))

    if not csv_files:
        print("\nNo CSV files found in Data/raw/")
        print("Add the real datasets when available.")
        return

    datasets = {}

    # Load every CSV
    for file in csv_files:

        print(f"\nLoading: {file.name}")

        df = load_dataset(file)

        if df is not None:
            datasets[file.stem] = df

            print(f"Rows: {len(df)}")
            print(f"Start: {df['date'].min().date()}")
            print(f"End:   {df['date'].max().date()}")

    if not datasets:
        print("\nNo usable datasets found.")
        return

    # Find common date range
    latest_start = max(
        df["date"].min()
        for df in datasets.values()
    )

    earliest_end = min(
        df["date"].max()
        for df in datasets.values()
    )

    print("\n" + "=" * 60)
    print("COMMON DATE RANGE")
    print("=" * 60)

    print(f"Earliest common date: {latest_start.date()}")
    print(f"Latest common date:   {earliest_end.date()}")

    if latest_start > earliest_end:
        print("\nNo overlapping date range found.")
        return

    print("\nAll datasets have an overlapping period.")

    # Create dataset summary
    summary = pd.DataFrame({
        "dataset": list(datasets.keys()),
        "start_date": [
            df["date"].min()
            for df in datasets.values()
        ],
        "end_date": [
            df["date"].max()
            for df in datasets.values()
        ],
        "rows": [
            len(df)
            for df in datasets.values()
        ]
    })

    PROCESSED_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = PROCESSED_FOLDER / "dataset_summary.csv"

    summary.to_csv(
        output_file,
        index=False
    )

    print("\nSummary saved to:")
    print(output_file)


if __name__ == "__main__":
    main()