import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_FOLDER = BASE_DIR / "Data" / "processed"

INPUT_FILE = PROCESSED_FOLDER / "cargocast_ml_dataset.csv"


def main():

    print("=" * 70)
    print("CARGOCAST TIME-BASED DATA SPLIT")
    print("=" * 70)

    df = pd.read_csv(INPUT_FILE)

    df["date"] = pd.to_datetime(df["date"])

    df = df.sort_values("date").reset_index(drop=True)

    total_rows = len(df)

    train_end = int(total_rows * 0.70)
    validation_end = int(total_rows * 0.85)

    train = df.iloc[:train_end].copy()
    validation = df.iloc[
        train_end:validation_end
    ].copy()
    test = df.iloc[
        validation_end:
    ].copy()

    print("\nDATASET SIZES")
    print("-" * 70)

    print(f"Total:      {len(df)}")
    print(f"Train:      {len(train)}")
    print(f"Validation: {len(validation)}")
    print(f"Test:       {len(test)}")

    print("\nDATE RANGES")
    print("-" * 70)

    print(
        f"Train:      "
        f"{train['date'].min().date()} → "
        f"{train['date'].max().date()}"
    )

    print(
        f"Validation: "
        f"{validation['date'].min().date()} → "
        f"{validation['date'].max().date()}"
    )

    print(
        f"Test:       "
        f"{test['date'].min().date()} → "
        f"{test['date'].max().date()}"
    )

    train.to_csv(
        PROCESSED_FOLDER / "train.csv",
        index=False
    )

    validation.to_csv(
        PROCESSED_FOLDER / "validation.csv",
        index=False
    )

    test.to_csv(
        PROCESSED_FOLDER / "test.csv",
        index=False
    )

    print("\nFILES CREATED")
    print("-" * 70)

    print("Data/processed/train.csv")
    print("Data/processed/validation.csv")
    print("Data/processed/test.csv")

    print("\n" + "=" * 70)
    print("SPLIT COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()