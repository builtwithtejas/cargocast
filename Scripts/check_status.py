import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FOLDER = BASE_DIR / "Data" / "raw"


def main():

    file_path = RAW_FOLDER / "freight_indices_master_2022_2025.csv"

    df = pd.read_csv(file_path)

    df["Date"] = pd.to_datetime(df["Date"])

    status_columns = [
        "BDI_status",
        "BCI_status",
        "BPI_status",
        "BSI_status",
        "BHSI_status"
    ]

    for column in status_columns:

        filled_rows = df[
            df[column].astype(str).str.lower() != "real"
        ]

        print("\n" + "=" * 60)
        print(column)
        print("=" * 60)

        if filled_rows.empty:
            print("No non-real observations.")
        else:
            print(
                filled_rows[
                    ["Date", column]
                ].to_string(index=False)
            )


if __name__ == "__main__":
    main()
