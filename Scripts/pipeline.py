import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_FOLDER = BASE_DIR / "Scripts"


def run_script(script_name):
    """Run a Python script and stop if it fails."""

    script_path = SCRIPTS_FOLDER / script_name

    print("\n" + "=" * 60)
    print(f"RUNNING: {script_name}")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=BASE_DIR
    )

    if result.returncode != 0:
        print(f"\nScript failed: {script_name}")
        sys.exit(result.returncode)


def main():

    print("=" * 60)
    print("CARGOCAST DATA PIPELINE")
    print("=" * 60)

    scripts = [
        "audit_data.py",
        "clean_data.py",
        "merge_data.py",
        "load_to_database.py"
    ]

    for script in scripts:
        run_script(script)
    # Feature Engineer stage: build the authoritative Joined Feature Table.
    feature_script = BASE_DIR / "features" / "feature_engineering.py"
    print("\n" + "=" * 60)
    print("RUNNING: features/feature_engineering.py")
    print("=" * 60)
    result = subprocess.run([sys.executable, str(feature_script)], cwd=BASE_DIR)
    if result.returncode != 0:
        print("\nFeature engineering failed.")
        sys.exit(result.returncode)

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()