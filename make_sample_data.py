"""Generate a synthetic test-log CSV (no real factory data)."""
import random
import sys

import pandas as pd

random.seed(7)
STATIONS = ["ST-01", "ST-02", "ST-03", "ST-04"]
FAIL_PROFILE = {"ST-01": 0.02, "ST-02": 0.03, "ST-03": 0.22, "ST-04": 0.04}
CODES = {"ST-03": ["COM-101", "COM-101", "COM-204", "PWR-007"]}
DEFAULT_CODES = ["PWR-007", "CAL-310", "OPT-050", "COM-101"]


def make(path: str, n: int = 800) -> None:
    rows = []
    for i in range(n):
        st = random.choice(STATIONS)
        fail = random.random() < FAIL_PROFILE[st]
        rows.append(
            {
                "serial": f"SN{i:05d}",
                "station": st,
                "timestamp": f"2026-11-01 {8 + i % 10:02d}:{i % 60:02d}",
                "result": "FAIL" if fail else "PASS",
                "error_code": random.choice(CODES.get(st, DEFAULT_CODES)) if fail else "",
            }
        )
    df = pd.DataFrame(rows)
    df = pd.concat([df, df.sample(10, random_state=1)])  # duplicates
    df.loc[df.sample(6, random_state=2).index[:6], "serial"] = None  # invalid rows
    df.to_csv(path, index=False)


if __name__ == "__main__":
    make(sys.argv[1] if len(sys.argv) > 1 else "data/sample_logs.csv")
