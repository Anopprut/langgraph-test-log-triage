"""LangGraph workflow that triages factory test logs.

load_and_validate -> classify -> aggregate -> (route) -> investigate | all_clear -> report
"""
import os
from typing import Optional, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

FAIL_RATE_THRESHOLD = 0.05

# Maps an error code prefix to a failure category and a first-line hint.
KNOWLEDGE_BASE = {
    "PWR": ("Power", "Check supply rail and fixture contact; compare against the golden unit."),
    "COM": ("Communication", "Check cable and connector wear; re-run the link test on a second tester."),
    "CAL": ("Calibration", "Verify instrument calibration date and reference standard."),
    "OPT": ("Optical", "Inspect the optical connector for contamination; clean and retest."),
}


class TriageState(TypedDict, total=False):
    csv_path: str
    df: pd.DataFrame
    dropped: dict
    by_station: pd.DataFrame
    fail_rate: float
    worst_station: Optional[str]
    top_category: Optional[str]
    analysis: str
    report: str


def load_and_validate(state: TriageState) -> TriageState:
    df = pd.read_csv(state["csv_path"])
    n0 = len(df)
    df = df.dropna(subset=["serial", "station", "result"])
    n_invalid = n0 - len(df)
    n1 = len(df)
    df = df.drop_duplicates(subset=["serial", "station", "timestamp"])
    return {"df": df, "dropped": {"invalid": n_invalid, "duplicates": n1 - len(df)}}


def classify(state: TriageState) -> TriageState:
    df = state["df"].copy()
    prefix = df["error_code"].fillna("").str[:3]
    df["category"] = prefix.map(lambda p: KNOWLEDGE_BASE.get(p, ("Other", ""))[0])
    df.loc[df["result"] == "PASS", "category"] = "-"
    return {"df": df}


def aggregate(state: TriageState) -> TriageState:
    df = state["df"]
    g = df.groupby("station")["result"].agg(
        total="count", fails=lambda s: (s == "FAIL").sum()
    )
    g["fail_rate"] = g["fails"] / g["total"]
    g = g.sort_values("fail_rate", ascending=False)
    fails = df[df["result"] == "FAIL"]
    return {
        "by_station": g,
        "fail_rate": float(g["fails"].sum() / g["total"].sum()),
        "worst_station": g.index[0] if len(g) else None,
        "top_category": fails["category"].mode().iat[0] if len(fails) else None,
    }


def route(state: TriageState) -> str:
    return "investigate" if state["fail_rate"] > FAIL_RATE_THRESHOLD else "all_clear"


def _rule_based_analysis(state: TriageState) -> str:
    hint = next(
        (h for c, h in KNOWLEDGE_BASE.values() if c == state["top_category"]),
        "No matching knowledge-base entry; escalate to an engineer.",
    )
    return (
        f"Most failures are '{state['top_category']}' and concentrate on station "
        f"{state['worst_station']}. Suggested first step: {hint}"
    )


def investigate(state: TriageState) -> TriageState:
    """Use an LLM when an API key is set, otherwise fall back to the rules."""
    analysis = _rule_based_analysis(state)
    if os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(model=os.getenv("TRIAGE_MODEL", "gpt-4o-mini"), temperature=0)
            prompt = (
                "You are a test engineer. Given this station summary, give a short "
                "root-cause hypothesis and two next checks.\n"
                f"{state['by_station'].head(5).to_string()}\n"
                f"Top failure category: {state['top_category']}\n"
                f"Rule-based hint: {analysis}"
            )
            analysis = llm.invoke(prompt).content
        except Exception as exc:  # keep the pipeline running if the LLM fails
            analysis += f" (LLM unavailable: {exc.__class__.__name__})"
    return {"analysis": analysis}


def all_clear(state: TriageState) -> TriageState:
    return {"analysis": "Fail rate is within the threshold. No action needed."}


def report(state: TriageState) -> TriageState:
    lines = [
        "# Test-Log Triage Report",
        "",
        f"- Overall fail rate: {state['fail_rate']:.1%} (threshold {FAIL_RATE_THRESHOLD:.0%})",
        f"- Rows dropped: {state['dropped']['invalid']} invalid, "
        f"{state['dropped']['duplicates']} duplicate",
        "",
        "## By station",
        state["by_station"].round(3).to_markdown()
        if _has_tabulate()
        else state["by_station"].round(3).to_string(),
        "",
        "## Analysis",
        state["analysis"],
    ]
    return {"report": "\n".join(lines)}


def _has_tabulate() -> bool:
    try:
        import tabulate  # noqa: F401

        return True
    except ImportError:
        return False


def build_graph():
    g = StateGraph(TriageState)
    for name, fn in [
        ("load_and_validate", load_and_validate),
        ("classify", classify),
        ("aggregate", aggregate),
        ("investigate", investigate),
        ("all_clear", all_clear),
        ("report", report),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "load_and_validate")
    g.add_edge("load_and_validate", "classify")
    g.add_edge("classify", "aggregate")
    g.add_conditional_edges("aggregate", route, ["investigate", "all_clear"])
    g.add_edge("investigate", "report")
    g.add_edge("all_clear", "report")
    g.add_edge("report", END)
    return g.compile()
