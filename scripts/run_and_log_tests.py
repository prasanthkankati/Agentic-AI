import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    # 1) Print planned actions from generated tests
    summary = ROOT / "scripts" / "test_action_summary.py"
    print("=== Planned test actions from generated suites ===\n")
    subprocess.run([sys.executable, str(summary)], check=False)

    # 2) Run pytest and stream output
    print("\n=== Running pytest (streaming output) ===\n")
    rv = subprocess.run([sys.executable, "-m", "pytest", "-q"], check=False)
    print(f"\npytest exited with code {rv.returncode}")
    sys.exit(rv.returncode)


if __name__ == "__main__":
    main()
