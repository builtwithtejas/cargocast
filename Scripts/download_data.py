import pandas as pd
from pathlib import Path
import requests


# Project folders
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FOLDER = BASE_DIR / "Data" / "raw"

RAW_FOLDER.mkdir(parents=True, exist_ok=True)


def download_csv(url, filename):
    """
    Download a CSV file from a URL and save it to Data/raw/
    """

    output_file = RAW_FOLDER / filename

    print(f"\nDownloading: {filename}")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        output_file.write_bytes(response.content)

        print(f"Saved: {output_file}")

    except requests.RequestException as e:
        print(f"Download failed: {e}")


def main():

    print("=" * 60)
    print("CARG0CAST DATA DOWNLOADER")
    print("=" * 60)

    print("\nRaw data folder:")
    print(RAW_FOLDER)

    print("\nNo datasets configured yet.")
    print("Add dataset URLs when the actual data sources are available.")


if __name__ == "__main__":
    main()