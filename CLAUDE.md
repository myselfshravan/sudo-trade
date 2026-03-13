# sudo-trade

AI-powered algorithmic trading system for Indian markets.

## Stack

- Python 3.13, uv for package management
- Async by default (asyncio)
- Broker APIs: Kite Connect, Groww (multi-broker, role-based)
- LLMs: Claude Opus 4.6 primary, OpenAI-compatible schema for any provider
- Pipeline: ingest data → analyze → generate signals → execute trades

## Architecture

**Everything is a plugin.** The core is just orchestration — an event bus and a plugin registry. Every layer (broker, data source, LLM, strategy, execution, interface) is independently swappable and can run in parallel.

**Event-driven.** Plugins communicate through the EventBus without knowing about each other. The Engine wires everything together.

**Deployment-agnostic.** Runs anywhere — local, VPS, cloud, as a daemon, behind an API, consumed by an OS-level agent.

```
src/
├── core/           # Engine, EventBus, PluginRegistry, Config
│   ├── engine.py   # Orchestrator — manages plugin lifecycle
│   ├── events.py   # Async event bus for decoupled communication
│   ├── registry.py # Plugin registry by category
│   └── config.py   # Env + .env + override config loader
├── brokers/        # Broker plugins (Kite, Groww) with role assignment
│   ├── base.py     # Broker protocol — DATA | EXECUTION | BOTH
│   ├── kite.py     # Kite Connect integration
│   └── groww.py    # Groww integration
├── providers/      # Data source plugins (news, Reddit, X, RSS, scrapers)
│   └── base.py     # Provider protocol — fetch + stream
├── analysis/       # Analysis plugins (sentiment, technical, social)
│   └── base.py     # Analyzer protocol — data in, Signal out
├── llm/            # LLM plugins (Claude, OpenAI-compatible)
│   └── base.py     # LLM protocol — OpenAI schema
├── strategy/       # Strategy plugins (hybrid decision engine)
│   └── base.py     # Strategy protocol — signals in, TradeSignal out
├── execution/      # Execution plugins (paper, live)
│   └── base.py     # Executor protocol — routes to brokers
├── interfaces/     # Interface plugins (CLI, API, websocket)
│   └── base.py     # Interface protocol
└── __main__.py     # Entry point
```

## Plugin System

Every plugin implements a Protocol with `name`, `start()`, `stop()`. Register with:
```python
engine.add("broker", KiteBroker(role=BrokerRole.EXECUTION))
engine.add("broker", GrowwBroker(role=BrokerRole.DATA))
```

Categories: `broker`, `provider`, `analyzer`, `llm`, `strategy`, `executor`, `interface`

## Data Flow

```
Providers (news, social, market data)
    ↓ emit RawData
Analyzers (sentiment, technical)
    ↓ emit Signal (type, symbol, value, confidence)
Strategy Engine
    ↓ emit TradeSignal (action, symbol, quantity, reasoning)
Executor (paper or live)
    ↓ routes to Broker by role
Broker (Kite for execution, Groww for data, etc.)
```

## Multi-Broker Design

Brokers have roles via `BrokerRole` flag:
- `BrokerRole.DATA` — market quotes, historical data
- `BrokerRole.EXECUTION` — order placement and management
- `BrokerRole.BOTH` — everything

Multiple brokers run simultaneously. E.g., Groww for signals, Kite for execution.

## Commands

- `uv run python -m src` — run the engine
- `uv add <pkg>` — add a dependency
- `uv sync` — sync dependencies

## Git

- Push via HTTPS to github.com/myselfshravan/sudo-trade
- Conventional commit prefixes: init, feat, fix, refactor, docs

## Docs

`/docs` — raw reference docs, broker API specs, strategy notes, architecture decisions. The AI agent's knowledge base.
