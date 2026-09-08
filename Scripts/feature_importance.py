import pandas as pd
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor


BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_FOLDER = BASE_DIR / "Data" / "processed"

TARGET = "freight_rate_per_tonne"


def main():

    print("=" * 70)
    print("CARGOCAST FEATURE IMPORTANCE")
    print("=" * 70)

    train = pd.read_csv(
        PROCESSED_FOLDER / "train.csv"
    )

    X = train.drop(
        columns=[TARGET, "date"]
    )

    y = train[TARGET]

    # Keep numerical features only
    X = X.select_dtypes(
        include=["number"]
    )

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X, y)

    importance = pd.DataFrame({
        "feature": X.columns,
        "importance": model.feature_importances_
    })

    importance = importance.sort_values(
        "importance",
        ascending=False
    )

    print("\nTOP 30 FEATURES")
    print("-" * 70)

    print(
        importance.head(30).to_string(
            index=False
        )
    )

    print("\n" + "=" * 70)
    print("FEATURE IMPORTANCE COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()