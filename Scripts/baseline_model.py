import pandas as pd
import numpy as np
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_FOLDER = BASE_DIR / "Data" / "processed"

TARGET = "freight_rate_per_tonne"


def evaluate_model(model, X, y, name):

    predictions = model.predict(X)

    mae = mean_absolute_error(y, predictions)
    rmse = np.sqrt(mean_squared_error(y, predictions))
    r2 = r2_score(y, predictions)

    print(f"\n{name}")
    print("-" * 70)
    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"R²:   {r2:.4f}")


def main():

    print("=" * 70)
    print("CARGOCAST BASELINE MODEL")
    print("=" * 70)

    train = pd.read_csv(
        PROCESSED_FOLDER / "train.csv"
    )

    validation = pd.read_csv(
        PROCESSED_FOLDER / "validation.csv"
    )

    test = pd.read_csv(
        PROCESSED_FOLDER / "test.csv"
    )

    # --------------------------------------------------
    # Separate target
    # --------------------------------------------------

    X_train = train.drop(
        columns=[TARGET, "date"]
    )

    X_validation = validation.drop(
        columns=[TARGET, "date"]
    )

    X_test = test.drop(
        columns=[TARGET, "date"]
    )

    y_train = train[TARGET]
    y_validation = validation[TARGET]
    y_test = test[TARGET]

    # --------------------------------------------------
    # Keep only numerical features
    # --------------------------------------------------

    numeric_columns = X_train.select_dtypes(
        include=["number"]
    ).columns

    X_train = X_train[numeric_columns]
    X_validation = X_validation[numeric_columns]
    X_test = X_test[numeric_columns]

    print(f"\nNumerical features: {len(numeric_columns)}")

    # --------------------------------------------------
    # Baseline 1: mean prediction
    # --------------------------------------------------

    mean_prediction = y_train.mean()

    validation_predictions = np.full(
        len(y_validation),
        mean_prediction
    )

    test_predictions = np.full(
        len(y_test),
        mean_prediction
    )

    print("\nMEAN BASELINE")
    print("-" * 70)

    print(
        f"Validation MAE: "
        f"{mean_absolute_error(y_validation, validation_predictions):.4f}"
    )

    print(
        f"Test MAE: "
        f"{mean_absolute_error(y_test, test_predictions):.4f}"
    )

    # --------------------------------------------------
    # Baseline 2: Random Forest
    # --------------------------------------------------

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )

    model.fit(
        X_train,
        y_train
    )

    evaluate_model(
        model,
        X_validation,
        y_validation,
        "Random Forest - Validation"
    )

    evaluate_model(
        model,
        X_test,
        y_test,
        "Random Forest - Test"
    )

    print("\n" + "=" * 70)
    print("BASELINE COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()