import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FOLDER = BASE_DIR / "Data" / "raw"

FEATURE_FILE = RAW_FOLDER / "freight_feature_table_v1.csv"


def check_rolling_mean(df, value_column, feature_column, window):

    expected = df[value_column].rolling(window).mean()

    comparison = pd.DataFrame({
        "actual": df[feature_column],
        "expected": expected
    })

    valid = comparison.dropna()

    differences = (
        valid["actual"] - valid["expected"]
    ).abs()

    mismatch_count = (differences > 0.000001).sum()

    print(f"\n{feature_column}")
    print(f"Checked values: {len(valid)}")
    print(f"Mismatches: {mismatch_count}")

    if mismatch_count > 0:
        print("\nFirst mismatches:")

        mismatch_indices = differences[
            differences > 0.000001
        ].index

        print(
            comparison.loc[mismatch_indices]
            .head(10)
            .to_string()
        )


def check_roc(df):

    expected = (
        (df["BDI"] / df["BDI"].shift(30)) - 1
    ) * 100

    comparison = pd.DataFrame({
        "actual": df["BDI_30d_roc"],
        "expected": expected
    })

    valid = comparison.dropna()

    differences = (
        valid["actual"] - valid["expected"]
    ).abs()

    mismatch_count = (differences > 0.000001).sum()

    print("\nBDI_30d_roc")
    print(f"Checked values: {len(valid)}")
    print(f"Mismatches: {mismatch_count}")

    if mismatch_count > 0:
        print("\nFirst mismatches:")

        mismatch_indices = differences[
            differences > 0.000001
        ].index

        print(
            comparison.loc[mismatch_indices]
            .head(10)
            .to_string()
        )


def main():

    print("=" * 70)
    print("ROLLING FEATURE VALIDATION")
    print("=" * 70)

    df = pd.read_csv(FEATURE_FILE)

    df["Date"] = pd.to_datetime(df["Date"])

    df = df.sort_values("Date").reset_index(drop=True)

    print(f"\nRows: {len(df)}")

    check_rolling_mean(
        df,
        "BDI",
        "BDI_7d_avg",
        7
    )

    check_rolling_mean(
        df,
        "BDI",
        "BDI_30d_avg",
        30
    )

    check_roc(df)

    print("\n" + "=" * 70)
    print("VALIDATION COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()