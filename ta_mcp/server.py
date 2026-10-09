"""stdio MCP server: numerical tools only; never writes broker orders."""
from threading import RLock
from mcp.server.fastmcp import FastMCP
from .core import Strategy, snapshot
from .backtest import Costs, backtest
from .data import dataset, list_datasets, fetch

mcp = FastMCP('Agentic MT5 Technical Analysis')
mt5_lock = RLock()

@mcp.tool()
def datasets() -> list[str]:
    """List CSV datasets available under TA_DATA_DIR."""
    return list_datasets()

@mcp.tool()
def analyze_csv(name: str, parameters: dict | None = None) -> dict:
    """Compute Supertrend, RSI, Bollinger, SMA/EMA and long/flat target from closed bars."""
    return snapshot(dataset(name), Strategy(**(parameters or {})))

@mcp.tool()
def evaluate_csv(name: str, parameters: dict | None = None, costs: dict | None = None) -> dict:
    """Backtest rule strategy using next-bar fills; returns aggregate metrics, not all trades."""
    result = backtest(dataset(name), Strategy(**(parameters or {})), Costs(**(costs or {})))
    return {k: v for k,v in result.items() if k not in ('trades','equity')}

@mcp.tool()
def analyze_mt5(symbol: str, timeframe: str = 'H1', count: int = 2000) -> dict:
    """Read broker closed bars from local Windows MT5 and calculate technical analysis."""
    with mt5_lock:
        return snapshot(fetch(symbol, timeframe, count))

@mcp.prompt()
def research_workflow(dataset_name: str) -> str:
    return (f'Analyze {dataset_name}. Call analyze_csv and evaluate_csv. Explain indicator agreement, '
            'conflicts, drawdown and cost assumptions. Distinguish the deterministic signal from '
            'your interpretation. Never invent prices or returns. Do not claim profitability from '
            'in-sample or synthetic data. End with LONG, FLAT or INSUFFICIENT_EVIDENCE and reasons.')


def main():
    mcp.run(transport='stdio')

if __name__ == '__main__':
    main()
