# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

Freqtrade is a Python crypto trading bot (GPLv3, Python >= 3.11) supporting many CEX/DEX exchanges via `ccxt`. It covers live trading, dry-run, backtesting, hyperopt, FreqAI (ML), plotting, and a FastAPI-based REST/WebSocket server with a bundled web UI. The installable CLI is `freqtrade` (entry point: `freqtrade.main:main`).

`ft_client/` is a separate sub-package (`freqtrade-client`) published alongside the main package — a thin REST client / CLI (`freqtrade-client`) for controlling a running bot. It has its own `pyproject.toml` and must be kept importable without the main package.

## Branches & PR target

- `develop` — active development, target ALL pull requests here.
- `stable` — latest release (this checkout is on `stable`).
- **Never** open PRs against `stable`.

## Environment & commands

This repo uses a local venv at `.venv/` (Python 3.13 per SETUP_RESUMO.md). Activate with `source .venv/bin/activate` before running tools, or invoke binaries directly from `.venv/bin/`.

### Tests

```bash
pytest                                          # whole suite
pytest tests/test_<file>.py                     # single file
pytest tests/test_<file>.py::test_<method>      # single test
pytest --random-order --cov=freqtrade --cov-config=.coveragerc tests/  # full CI-style run (see tests/pytest.sh)
```

`pyproject.toml` sets `asyncio_mode = "auto"` and pytest-xdist with `--dist loadscope` — async tests don't need explicit `@pytest.mark.asyncio`, and xdist groups tests by module scope. `tests/test_pip_audit.py` hits the network; skip it in offline contexts. `tests/exchange_online/` talks to real exchanges and is gated separately.

### Lint, format, types

```bash
ruff check .            # lint (line-length 100, mccabe max-complexity 12)
ruff format .           # formatter (replaces black)
mypy freqtrade          # type check (ignores build_helpers; tests excluded)
pre-commit run -a       # runs ruff, mypy, codespell, zizmor, schema-extractor, etc.
pre-commit install      # install the git hook
```

`build_helpers/extract_config_json_schema.py` runs in pre-commit and **writes files** — if the config schema (`freqtrade/config_schema/`) changes, the hook regenerates `schema.json` and fails until committed. Re-stage and commit after it runs; don't bypass.

### Running the bot locally

This checkout has an opinionated `bot.sh` wrapper and a configured `user_data/`:

```bash
./bot.sh start|stop|restart|status|logs|backtest|webserver|download
```

Direct CLI equivalents (after `source .venv/bin/activate`):

```bash
freqtrade trade -c user_data/config.json --dry-run
freqtrade backtesting -c user_data/config.json -s <Strategy> --timerange 20250301-20250401
freqtrade hyperopt -c user_data/config.json -s <Strategy> --hyperopt-loss SharpeHyperOptLoss -e 100
freqtrade download-data --exchange binance -t 5m --timerange 20240101-
freqtrade webserver -c user_data/config.json        # FreqUI at http://localhost:8080
freqtrade new-strategy -s MyStrategy                # scaffold from templates
freqtrade list-strategies / list-exchanges / list-freqaimodels / list-hyperoptloss
```

The current `user_data/config.json` points at `strategy: KellyOptimalStrategy` (in `user_data/strategies/`), exchange `binance` (spot, `dry_run: true`), SQLite DB at `user_data/tradesv3.sqlite`, and serves FreqUI on port 8080 with credentials in the config file.

## Architecture: the big picture

The bot is a single long-running process built around three layers that cross-cut every run mode (live, dry-run, backtest, hyperopt):

1. **`FreqtradeBot` (`freqtrade/freqtradebot.py`)** — live/dry-run orchestrator. Owns the `Exchange`, `IStrategy`, `Wallets`, `PairListManager`, `ProtectionManager`, `RPCManager`, and `DataProvider`. `process()` is one iteration of the trading loop; `Worker` (`worker.py`) is the surrounding loop + throttle + state machine (`State` enum: RUNNING / STOPPED / RELOAD_CONFIG). Backtesting (`optimize/backtesting.py`) and Hyperopt (`optimize/hyperopt/`) are **separate orchestrators** that reuse the same `IStrategy`, `Exchange`, and persistence layers but drive them against historical data instead of a live loop — when you modify strategy/exchange interfaces, check all three call sites.

2. **Pluggable components loaded by string name via resolvers (`freqtrade/resolvers/`).** `StrategyResolver`, `ExchangeResolver`, `PairListResolver`, `ProtectionResolver`, `FreqaiModelResolver`, `HyperOptLossResolver`, `IResolver` — they discover classes by walking user-configured paths (e.g. `user_data/strategies/`) plus the shipped `freqtrade/templates/`, `freqtrade/plugins/pairlist/`, `freqtrade/optimize/hyperopt_loss/`, etc. When adding a new pluggable component type, the pattern is: define an abstract base class, implement the resolver, register it in configuration.

3. **Persistence (`freqtrade/persistence/`)** — SQLAlchemy 2.x models (`Trade`, `Order`, `PairLock`, `KeyValueStore`, `CustomDataWrapper`). `Trade` has a class-level in-memory cache and a `use_db` flag; backtesting flips `use_db=False` so trades live in memory only. `LocalTrade` is the non-DB variant. Migrations are handled in `persistence/migrations.py` and run automatically at startup.

### Strategy interface (where users write code)

`freqtrade/strategy/interface.py` defines `IStrategy` (ABC). User strategies live in `user_data/strategies/` and implement `populate_indicators`, `populate_entry_trend`, `populate_exit_trend`, plus optional callbacks (`custom_stoploss`, `custom_entry_price`, `custom_exit`, `adjust_trade_position` for DCA, `confirm_trade_entry/exit`, `leverage`, `informative` pairs via the `@informative` decorator). `HyperStrategyMixin` (`strategy/hyper.py`) supplies the `IntParameter`/`DecimalParameter`/etc. hyperopt-able parameters. The strategy is passed the same `DataProvider` in all run modes.

Strategies are sandboxed through `strategy_safe_wrapper` — exceptions in user code are caught and logged, not raised, so never rely on an exception from user code propagating. Bugs in user strategies often surface as "signal not generated" rather than tracebacks.

### Exchange layer

`freqtrade/exchange/exchange.py` is a ~thick~ abstraction over `ccxt` with per-exchange subclasses (`binance.py`, `bybit.py`, `kraken.py`, `okx.py`, `hyperliquid.py`, etc.) overriding quirks (leverage tiers, funding fees, order params, candle fetching). Futures-specific behavior is mixed in via `MarginMode`/`TradingMode` branches rather than a separate class — when fixing a futures bug, grep for `trading_mode == TradingMode.FUTURES`. Websocket candle streaming is in `exchange_ws.py`.

### RPC / API / Web UI

`freqtrade/rpc/rpc.py` (`RPC` class) is the single source of truth for "what can be asked of a running bot" — `/status`, `/profit`, `/forceexit`, `/reload_config`, etc. Telegram (`telegram.py`), Webhook (`webhook.py`), Discord (`discord.py`), and the FastAPI server (`rpc/api_server/`) are all thin adapters over `RPC`. When adding a new bot-control command, add the method to `RPC` first, then surface it through each adapter that needs it. `RPCManager` fans out notifications to all enabled channels.

The REST API is versioned (`api_server/api_v1.py`, `api_schemas.py`, Pydantic models) and serves a prebuilt Vue web UI from `rpc/api_server/ui/installed/` after `freqtrade install-ui`.

### FreqAI

`freqtrade/freqai/` layers ML on top of a strategy: data kitchen (feature engineering), base prediction models (`prediction_models/`), optional RL (`RL/` via stable-baselines3). It's behind the `freqai` extra; code that imports from `freqtrade.freqai` must remain importable only when the extra is installed.

### Optimize / analysis

- `optimize/backtesting.py` — drives `IStrategy` against cached OHLCV; emits results to `user_data/backtest_results/`.
- `optimize/hyperopt/` — optuna-based parameter search; loss functions pluggable from `optimize/hyperopt_loss/`.
- `optimize/analysis/` + `data/btanalysis/` — loading and post-processing backtest outputs.
- `data/entryexitanalysis.py` — the `backtesting-analysis` subcommand; `lookahead_analysis` / `recursive_analysis` detect strategy bugs.

## Conventions worth knowing

- Line length 100 (ruff, flake8). Ruff is the authoritative formatter.
- Public methods should have reST-format docstrings (`:param xxx:`, `:return:`, `:raises:`). Use double-quoted docstrings.
- `freqtrade/vendor/` is vendored third-party code — excluded from pyright/ignored in rules; don't reformat.
- SQLAlchemy uses the mypy plugin; declarative models under `persistence/` will type-check differently than plain classes.
- Constants (run-time defaults, schema-adjacent constants, message types) live in `freqtrade/constants.py` — check there before introducing a new magic string.
- The config JSON schema is code-generated; edit Python definitions in `freqtrade/config_schema/`, not the emitted JSON.
- Tests import heavily from `tests/conftest.py` and `tests/conftest_trades*.py` — use these fixtures rather than rebuilding mocks.
