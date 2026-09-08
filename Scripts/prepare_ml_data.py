import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FOLDER = BASE_DIR / "Data" / "raw"

FILE = RAW_FOLDER / "maritime_freight_voyages_only (1).csv"

TARGET = "freight_rate_per_tonne"


def main():

    print("=" * 70)
    print("CARGOCAST ML DATASET INSPECTION")
    print("=" * 70)

    df = pd.read_csv(FILE)

    print(f"\nRows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    print("\nTARGET")
    print("-" * 70)

    print(f"Target: {TARGET}")
    print(f"Missing target values: {df[TARGET].isna().sum()}")

    print("\nTARGET STATISTICS")
    print("-" * 70)

    print(df[TARGET].describe())

    print("\nPOTENTIAL LEAKAGE COLUMNS")
    print("-" * 70)

    leakage_words = [
        "cost",
        "freight_rate",
        "revenue",
        "profit",
        "final",
        "actual"
    ]

    for column in df.columns:

        if column == TARGET:
            continue

        name = column.lower()

        if any(word in name for word in leakage_words):
            print(f"CHECK: {column}")

    print("\nCATEGORICAL COLUMNS")
    print("-" * 70)

    categorical = df.select_dtypes(
        include=["object", "category"]
    ).columns

    for column in categorical:
        print(
            f"{column}: "
            f"{df[column].nunique(dropna=True)} unique values"
        )

    print("\nNUMERICAL COLUMNS")
    print("-" * 70)

    numerical = df.select_dtypes(
        include=["number"]
    ).columns

    print(f"Numerical columns: {len(numerical)}")

    print("\nMISSING VALUES")
    print("-" * 70)

    missing = df.isna().sum()

    missing = missing[missing > 0].sort_values(
        ascending=False
    )

    if len(missing) == 0:
        print("No missing values.")

    else:
        print(missing.to_string())

    print("\n" + "=" * 70)
    print("INSPECTION COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()