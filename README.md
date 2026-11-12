# LangGraph Test-Log Triage

A small LangGraph workflow that triages factory test logs: it validates the data, groups failures, routes by fail rate, and proposes a first check. It was inspired by log-analysis tooling I build for production test, and runs on **synthetic data only**.

```
START -> load_and_validate -> classify -> aggregate --(fail rate > 5%)--> investigate --> report -> END
                                                    \--(otherwise)------> all_clear  --/
```

| Node | What it does |
|---|---|
| `load_and_validate` | Reads the CSV, drops rows with missing fields and duplicate serial/station/timestamp |
| `classify` | Maps error-code prefixes (PWR, COM, CAL, OPT) to failure categories |
| `aggregate` | Fail rate per station, worst station, top failure category |
| `route` | Conditional edge on the overall fail rate |
| `investigate` | Root-cause hypothesis: an LLM if `OPENAI_API_KEY` is set (via `langchain-openai`), otherwise a rule-based knowledge base |
| `report` | Writes a Markdown report |

## Run

```bash
pip install -r requirements.txt
python make_sample_data.py          # synthetic logs with one bad station (ST-03)
python main.py                      # prints and writes report.md
python -m pytest -q                 # 3 tests
```

Optional LLM step: `pip install langchain-openai` and set `OPENAI_API_KEY` (model via `TRIAGE_MODEL`, default `gpt-4o-mini`). If the call fails, the pipeline falls back to the rule-based analysis.

## Example output

```
Overall fail rate: 8.4% (threshold 5%)
Rows dropped: 6 invalid, 10 duplicate
ST-03 fail rate 24.7% ... Most failures are 'Communication' and concentrate on station ST-03.
```

## Design notes
- State is a typed dict, so each node is a pure function that is easy to test.
- The LLM is optional and isolated in one node; the graph runs and is tested without network access.
- Possible next steps: retrieval over past failure-analysis reports (RAG), a human-approval node before corrective actions, and a FastAPI endpoint.
