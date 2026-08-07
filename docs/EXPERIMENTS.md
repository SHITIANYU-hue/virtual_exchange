# Experiments

`run_experiment.py` drives the whole agent ecosystem through a fixed number
of ReAct cycles against a running backend and writes every prompt, action,
market snapshot, and audit verdict to disk. This is the guide to running
it; for the backend's HTTP API itself see [`API.md`](API.md). All commands
below assume your working directory is the repo root.

## Quick start

```bash
docker compose up -d
python3 agents/run.py --setup                     # register all 10 agents
python3 run_experiment.py --cycles 50 --delay 10   # live prices, 50 cycles
```

Set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY` with `LLM_PROVIDER=openai`) in
`.env` first — every cycle makes one LLM call per agent.

## CLI reference

| Flag | Meaning |
|---|---|
| `--cycles N` | Number of cycles to run |
| `--delay S` | Delay between cycles, in seconds |
| `--model NAME` | LLM model override (default: `LLM_MODEL` env var, or `claude-sonnet-4-20250514`) |
| `--no-reset` | Don't reset agent memories before the run |
| `--hard-reset` | **Destructive.** Wipes every agent's balances/positions/orders/messages/tokens/pools in the DB and re-registers everyone fresh, in addition to resetting memory. Use for a clean baseline; overrides `--no-reset` |
| `--output-dir PATH` | Custom output directory (default: `experiment_logs/YYYYMMDD_HHMMSS/`) |
| `--start-cycle N` | Starting cycle number, for continuing an interrupted run |
| `--label TEXT` | Human-readable suffix on the output directory, e.g. `--label auditor-haiku-5cyc` → `experiment_logs/20260718_HHMMSS_auditor-haiku-5cyc` |
| `--world {A,B,C}` | Historical replay world (blind label). Requires the backend running with `PRICE_MODE=replay REPLAY_WORLD=<this>`; each cycle advances the replay by one historical hour. See [`ARCHITECTURE.md`](ARCHITECTURE.md), section 12 |

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Overridden per-run by `--model` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | — | LLM provider credentials |
| `AUDITOR_MODE` | `block_and_flag` | `block_and_flag`, or `log_only` (the judge still scores every action but never blocks) |
| `AUDITOR_ENABLED` | `1` | Set to `0` to skip the judge pipeline entirely — a stronger, faster "off" than `log_only`, which still runs the LLM judge on every action |
| `AUDITOR_LLM_MODEL` | `claude-haiku-4-5-20251001` | Model used for the auditor's LLM-judge pass |

## `configs/`

One preset shell script per paper experiment arm — each sets the right env
vars, starts the backend in the right price mode, and calls
`run_experiment.py` with the flags used to produce the results in
[`../analysis/`](../analysis/):

| Script | World | Auditor |
|---|---|---|
| `world_a_auditor.sh` / `world_b_auditor.sh` / `world_c_auditor.sh` | A / B / C (replay) | ON (`block_and_flag`) |
| `world_a_noauditor.sh` / `world_b_noauditor.sh` / `world_c_noauditor.sh` | A / B / C (replay) | OFF (`AUDITOR_ENABLED=0`) |
| `regular_market_auditor.sh` | live prices | ON |
| `regular_market_norestriction.sh` | live prices | `log_only` (scored but never blocks) |

```bash
./configs/world_a_auditor.sh
```

## Output structure

```
experiment_logs/YYYYMMDD_HHMMSS[_label]/
├── config.json                 # experiment parameters: cycles, model, world, agent roster
├── portfolio_performance.csv   # per-cycle portfolio value for every agent
├── messages.csv                # every broadcast + DM, with sender/recipient/phase
├── prompts/                    # full ReAct prompt sent to each agent each cycle
│   └── {agent}_cycle_{n}.txt
├── actions/                    # raw + parsed LLM response for each agent each cycle
│   └── {agent}_cycle_{n}.json
├── status/                     # market snapshot at the end of each cycle
│   └── cycle_{n}.json
├── errors/                     # any LLM or execution failure, if one occurred
│   └── {agent}_cycle_{n}.txt
├── audit_report.json           # aggregate flag/block rates, manipulation categories, per-agent risk
└── audit_events.csv            # every individual audit verdict (omitted if AUDITOR_ENABLED=0)
```

`experiment_logs/` itself is gitignored — nothing under it is committed.
[`../sample_data/`](../sample_data/) is a trimmed, checked-in copy of one
real run (everything above except `prompts/`/`actions/`, which are large
raw LLM I/O) kept as a concrete example and as the fixture
[`../analysis/test_analyze_run.py`](../analysis/test_analyze_run.py) runs
against. The complete raw dataset across every run is published
separately — see [`../sample_data/README.md`](../sample_data/README.md).

## Network-outage resilience

`call_llm()` retries connection errors and 429/5xx/overloaded responses with
exponential backoff (5s → 10s → 20s → 40s, 4 attempts) before giving up on an
agent's turn; non-transient errors (auth, bad request) raise immediately. If
≥50% of agents fail in a single cycle, the runner treats it as a likely
network outage and backs off the *next* cycle's start (`delay × 2^consecutive_bad_cycles`,
capped at 300s) instead of retrying at the normal cadence — the backoff
resets once a cycle succeeds normally. If every failure in such a cycle is a
positively-identified *permanent* error (bad auth, insufficient quota/balance
— not a network blip), the runner aborts instead of backing off forever.
OpenAI complicates the permanent/transient split: it returns HTTP 429 for
both ordinary rate limiting (retry) and quota exhaustion (permanent),
distinguishable only via the error body's `code` field — `insufficient_quota`
is classified as permanent.

## Analyzing results

```bash
python3 analysis/analyze_run.py experiment_logs/20260101_120000_my-run
```

See [`../analysis/`](../analysis/) for the analysis script, its unit tests,
and the curated write-ups it backs.
