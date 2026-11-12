import pandas as pd

from triage.graph import build_graph


def _run(tmp_path, rows):
    path = tmp_path / "logs.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return build_graph().invoke({"csv_path": str(path)})


def _row(i, station, result, code=""):
    return {"serial": f"S{i}", "station": station, "timestamp": "t", "result": result, "error_code": code}


def test_high_fail_rate_routes_to_investigate(tmp_path):
    rows = [_row(i, "ST-A", "FAIL", "COM-101") for i in range(10)] + [_row(99, "ST-B", "PASS")]
    out = _run(tmp_path, rows)
    assert out["worst_station"] == "ST-A"
    assert out["top_category"] == "Communication"
    assert "Suggested first step" in out["analysis"]


def test_low_fail_rate_is_all_clear(tmp_path):
    rows = [_row(i, "ST-A", "PASS") for i in range(50)]
    out = _run(tmp_path, rows)
    assert "No action needed" in out["analysis"]


def test_duplicates_and_invalid_rows_are_dropped(tmp_path):
    rows = [_row(1, "ST-A", "PASS"), _row(1, "ST-A", "PASS"), {**_row(2, "ST-A", "PASS"), "serial": None}]
    out = _run(tmp_path, rows)
    assert out["dropped"] == {"invalid": 1, "duplicates": 1}
