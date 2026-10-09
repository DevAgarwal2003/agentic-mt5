# Validation record

Completed in Linux, Python 3.12:

- Editable install with MCP v1 and optional agent dependencies succeeded.
- `python -m pytest -q`: **10 passed**.
- Real MCP subprocess initialize, tool discovery, CSV analysis and evaluation succeeded.
- Out-of-directory CSV request returned a tool error.
- Synthetic data CLI backtest and replay export succeeded.
- Indicator tests verify RSI edge values, Wilder seed, Bollinger population deviation and causal prefix invariance.
- Execution tests verify next-bar timing, stop-first ambiguity, adverse stop gaps and portfolio accounting.

Not executed here:

- MetaEditor compilation of TAReplay.mq5.
- Broker connection, MT5 historical-data acquisition, or visual Strategy Tester run.
- Remote LLM inference with an API credential.

The synthetic example outputs are software fixtures, not empirical evidence about a stock or trading performance. Dependency versions recorded in tested-versions.txt describe this test environment; pyproject.toml defines supported installation ranges.
