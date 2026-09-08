import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FOLDER = BASE_DIR / "Data" / "raw"

FEATURE_FILE = RAW_FOLDER / "freight_feature_table_v1.csv"


def main():

    print("=" * 70)
    print("CARGOCAST FEATURE LEAKAGE CHECK")
    print("=" * 70)

    df = pd.read_csv(FEATURE_FILE)

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    print(f"\nRows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    print("\nPOTENTIAL FUTURE-LOOKING FEATURES")
    print("-" * 70)

    suspicious_words = [
        "future",
        "next",
        "lead",
        "target",
        "tomorrow",
        "forecast",
        "actual"
    ]

    found = []

    for column in df.columns:

        column_lower = column.lower()

        for word in suspicious_words:

            if word in column_lower:
                found.append(column)
                break

    if found:
        for column in found:
            print(f"WARNING: {column}")
    else:
        print("No obviously future-looking column names found.")

    print("\nTARGET-LIKE COLUMNS")
    print("-" * 70)

    target_words = [
        "freight_rate",
        "target",
        "y"
    ]

    for column in df.columns:

        name = column.lower()

        if any(word in name for word in target_words):
            print(f"Potential target: {column}")

    print("\nLAG / ROLLING FEATURES")
    print("-" * 70)

    lag_columns = [
        column
        for column in df.columns
        if "lag" in column.lower()
    ]

    rolling_columns = [
        column
        for column in df.columns
        if "avg" in column.lower()
        or "rolling" in column.lower()
        or "roc" in column.lower()
        or "vol" in column.lower()
    ]

    print(f"Lag features: {len(lag_columns)}")
    print(f"Rolling/derived features: {len(rolling_columns)}")

    print("\nFEATURES USING CURRENT-DATE VALUES")
    print("-" * 70)

    for column in df.columns:

        if column in ["Date"]:
            continue

        if column.lower() in [
            "bdi",
            "bci",
            "bpi",
            "bsi",
            "bhsi"
        ]:
            print(
                f"NOTE: {column} contains the index value "
                f"for the current date."
            )

    print("\n" + "=" * 70)
    print("LEAKAGE CHECK COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()