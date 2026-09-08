import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FOLDER = BASE_DIR / "Data" / "raw"
PROCESSED_FOLDER = BASE_DIR / "Data" / "processed"

INPUT_FILE = RAW_FOLDER / "maritime_freight_voyages_only (1).csv"
OUTPUT_FILE = PROCESSED_FOLDER / "cargocast_ml_dataset.csv"

TARGET = "freight_rate_per_tonne"


def main():

    print("=" * 70)
    print("BUILDING CARGOCAST ML DATASET")
    print("=" * 70)

    PROCESSED_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )

    df = pd.read_csv(INPUT_FILE)

    print(f"\nOriginal shape: {df.shape}")

    # --------------------------------------------------
    # 1. Parse and sort dates
    # --------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df = df.sort_values("date").reset_index(drop=True)

    # --------------------------------------------------
    # 2. Remove obvious leakage
    # --------------------------------------------------

    columns_to_remove = [
        "total_voyage_cost",
        "cyclone_names",
        "weather_source",
        "cyclone_source",
        "market_source",
        "port_source",
        "data_source_notes",
        "wb_coal_benchmark_desc",
        "wb_iron_ore_benchmark_desc"
    ]

    existing_columns = [
        column
        for column in columns_to_remove
        if column in df.columns
    ]

    df = df.drop(
        columns=existing_columns
    )

    print(
        f"\nRemoved columns: "
        f"{len(existing_columns)}"
    )

    for column in existing_columns:
        print(f"  - {column}")

    # --------------------------------------------------
    # 3. Remove rows without target/date
    # --------------------------------------------------

    before = len(df)

    df = df.dropna(
        subset=["date", TARGET]
    )

    print(
        f"\nRows removed because of "
        f"missing date/target: "
        f"{before - len(df)}"
    )

    # --------------------------------------------------
    # 4. Convert categorical columns
    # --------------------------------------------------

    categorical_columns = df.select_dtypes(
        include=["object", "string", "category"]
    ).columns.tolist()

    categorical_columns = [
        column
        for column in categorical_columns
        if column not in ["date"]
    ]

    print(
        f"\nCategorical columns: "
        f"{len(categorical_columns)}"
    )

    # Fill categorical missing values
    for column in categorical_columns:

        df[column] = df[column].fillna(
            "Unknown"
        )

    # --------------------------------------------------
    # 5. Fill numerical missing values
    # --------------------------------------------------

    numerical_columns = df.select_dtypes(
        include=["number"]
    ).columns.tolist()

    numerical_columns = [
        column
        for column in numerical_columns
        if column != TARGET
    ]

    for column in numerical_columns:

        if df[column].isna().sum() > 0:

            median_value = df[column].median()

            df[column] = df[column].fillna(
                median_value
            )

    # --------------------------------------------------
    # 6. Save
    # --------------------------------------------------

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print(
        f"\nFinal shape: {df.shape}"
    )

    print(
        f"\nSaved to:\n{OUTPUT_FILE}"
    )

    print("\nTARGET")
    print("-" * 70)

    print(df[TARGET].describe())

    print("\n" + "=" * 70)
    print("ML DATASET CREATED")
    print("=" * 70)


if __name__ == "__main__":
    main()