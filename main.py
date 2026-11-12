import argparse
from pathlib import Path

from triage.graph import build_graph


def main() -> None:
    p = argparse.ArgumentParser(description="Triage a test-log CSV with a LangGraph workflow")
    p.add_argument("csv", nargs="?", default="data/sample_logs.csv")
    p.add_argument("-o", "--out", default="report.md")
    args = p.parse_args()

    result = build_graph().invoke({"csv_path": args.csv})
    Path(args.out).write_text(result["report"], encoding="utf-8")
    print(result["report"])


if __name__ == "__main__":
    main()
