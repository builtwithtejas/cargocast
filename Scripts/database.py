import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_FOLDER = BASE_DIR / "Data"
DATABASE_FILE = DATABASE_FOLDER / "cargocast.db"


def create_database():
    """Create the CargoCast SQLite database."""

    DATABASE_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(DATABASE_FILE)

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_name TEXT NOT NULL,
            source TEXT,
            start_date TEXT,
            end_date TEXT,
            row_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS freight_indices (
            date TEXT PRIMARY KEY,
            bdi REAL,
            bci REAL,
            bpi REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commodity_prices (
            date TEXT PRIMARY KEY,
            iron_ore REAL,
            coking_coal REAL,
            bunker_fuel REAL
        )
    """)

    connection.commit()
    connection.close()

    print("Database created successfully.")
    print(f"Location: {DATABASE_FILE}")


def main():
    create_database()


if __name__ == "__main__":
    main()