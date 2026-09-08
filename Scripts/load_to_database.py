import sqlite3
import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_FOLDER = BASE_DIR / "Data" / "processed"
DATABASE_FILE = BASE_DIR / "Data" / "cargocast.db"


def load_csv_to_database(file_path, connection):
    """Load one processed CSV into SQLite."""

    print(f"\nLoading: {file_path.name}")

    try:
        df = pd.read_csv(file_path)

        if df.empty:
            print("Dataset is empty. Skipping.")
            return

        table_name = file_path.stem.lower()

        df.to_sql(
            table_name,
            connection,
            if_exists="replace",
            index=False
        )

        print(f"Table created: {table_name}")
        print(f"Rows loaded: {len(df)}")

    except Exception as error:
        print(f"Failed to load {file_path.name}: {error}")


def main():

    print("=" * 60)
    print("CARGOCAST DATABASE LOADER")
    print("=" * 60)

    if not PROCESSED_FOLDER.exists():
        print("\nProcessed folder not found.")
        return

    csv_files = list(PROCESSED_FOLDER.glob("*.csv"))

    if not csv_files:
        print("\nNo processed CSV files found.")
        print("Add cleaned datasets to Data/processed/ first.")
        return

    connection = sqlite3.connect(DATABASE_FILE)

    for file in csv_files:
        load_csv_to_database(file, connection)

    connection.commit()
    connection.close()

    print("\nDatabase loading complete.")


if __name__ == "__main__":
    main()