# EDP Research Contract

This document defines the contract every EDP research workflow must follow.
It is intentionally stricter than a README: new research can be experimental,
but it must expose the same shape of target, data boundary, outputs, CLI, and
validation so later work can be compared and maintained.

## 1. Scope

Every folder under `research/` must declare:

- the research question as a probability target;
- the prediction universe;
- the forecast horizon;
- the label definition;
- the data sources and cache boundary;
- the train/predict split;
- the output files;
- the CLI commands;
- the validation evidence and known limits.

If any item is unknown, the workflow must say so explicitly in its README and
keep the default command conservative.

## 2. EDP Method Boundary

An EDP research workflow is not just a data script. It must map to this stack:

| Layer | Required Meaning | Typical Output |
| --- | --- | --- |
| Probability | estimate `P(event)` for a clear future event | probability column |
| Flow | compare probability across dates or model windows | `prob_flow_pp`, momentum fields |
| Domain Awareness | add context, confirmation, or regime information | breadth, regime, confirmation state |
| Allocation Readiness | classify action state without pretending to trade | dashboard group or signal state |

The workflow may stop before allocation, but it must not skip the probability
target or mix target, feature, and dashboard interpretation into one opaque
score.

## 3. Target And Label Contract

Before adding features or models, define the target in this form:

```text
P(entity satisfies event over the next H trading days | information available at date T)
```

Required fields:

- `entity`: stock, theme, industry, pair, portfolio candidate, or another named universe item.
- `event`: binary event used for training and evaluation.
- `horizon`: one integer or a documented set such as `1,3,5`.
- `baseline`: the comparison class, such as all themes that day, own industry, or own theme.
- `label_column`: stable column name, for example `label_top_20pct_3d`.

Rules:

- Do not start from a model name. Start from the label.
- Do not use latest-only fields as historical training labels or features.
- Do not change an existing label silently. Add a new label column or document a breaking change.
- If multiple labels exist, the CLI must expose the selected target.

## 4. Data Contract

Each workflow must separate these data classes:

| Class | Meaning | May Be Used For Training |
| --- | --- | --- |
| Historical panel | point-in-time features available at date T | yes |
| Forward label | future return/outcome after date T | label only |
| Latest tail | unlabeled rows for current prediction | prediction only |
| Latest confirmation | current breadth, flow, news, or metadata | dashboard only unless point-in-time history exists |
| Cache | local copy of remote source data | yes, if timestamp/data boundary is clear |

Rules:

- Remote data calls must have cache paths and refresh flags.
- A-share daily OHLCV should use the shared EDP DuckDB warehouse maintained by
  `edp data update`: unadjusted prices in `stock_daily_raw`. Adjustment factors
  are refreshed separately by `edp data update-factors` into
  `stock_adj_factor`; adjusted views are derived only at read time.
- A-share universes must be derived from the shared AkShare metadata cache,
  including current code/name, Shanghai/Shenzhen delist tables, and cached name
  change tables. Workflow-local `universe.csv` files are exports, not truth
  sources.
- `stock_daily_raw` must persist completed trading days only. If a read request
  includes the current date, the data access layer may append an in-memory live
  AkShare spot snapshot before adjustment, but must not write that row to DuckDB.
- Data freshness must be represented separately from raw bars in
  `market_data_sync_status`, keyed by `stock_code + period`, with
  `reliable_data_time` marking the latest completed/reliable data boundary in
  data time, not the wall-clock time when the sync was checked.
  Intraday periods should mark the previous period reliable when a newer bar is
  observed; after the 15:03 close boundary, the last observed bar may be marked
  reliable even if no newer bar arrives.
- Current constituents are not historical constituents unless a point-in-time snapshot exists.
- Every output CSV must include the date or snapshot timestamp needed to audit its time boundary.
- Fallback sources must be documented, especially when they share the same upstream endpoint.
- A-share daily market data currently uses AkShare as the remote provider. Do
  not add another daily OHLCV provider without first extending the shared DuckDB
  warehouse contract and adding source audit fields.

## 5. No-Lookahead Rules

The workflow must prevent these leaks:

- using future return columns as features;
- training on rows whose labels are unavailable at prediction date;
- using current membership as historical membership without saying it is a live approximation;
- merging latest breadth or summary metadata into historical features before a point-in-time history exists;
- evaluating the latest unlabeled prediction as if it were a backtest row.

If the workflow deliberately uses a live approximation, it must include a
`Data Boundary` or `Known Limits` section in its README.

## 6. CLI Contract

Every research direction should support the same command shape:

```powershell
edp <area> daily
edp <area> build
edp <area> rank
edp <area> latest-breadth
edp <area> dashboard
```

Use only the commands that make sense. For example, a workflow without breadth
does not need `latest-breadth`, but it must still document why.

Required CLI behavior:

- `daily` runs the complete practical workflow.
- `build` creates the feature/label panel.
- `rank` creates model predictions or walk-forward rankings.
- `dashboard` creates human-readable grouped outputs.
- Daily orchestrators should read research parameters from the workflow config file, not from a long CLI flag list.
- Low-level composable scripts may expose `--use-cache`, `--refresh-*`, `--start-date`, `--top-n`, `--model`, and `--output*` when the underlying script supports them.
- Commands must print the files they produce.

## 7. Output Contract

A complete workflow should produce:

- panel CSV: feature and label rows;
- rank CSV: all scored rows;
- latest rank CSV: current prediction candidates;
- dashboard CSV: grouped current view;
- dashboard Markdown: readable daily report;
- summary JSON: parameters, dates, counts, metrics, and outputs.

Minimum columns for rank-like outputs:

```text
date, entity id/name, probability, rank, signal_state
```

Recommended probability-flow columns:

```text
prob_flow_pp, prob_momentum_3d_pp, prob_momentum_5d_pp, flow_direction
```

Dashboard group names must be stable enough for downstream scripts. If a group
is renamed, document the migration.

## 8. Validation Contract

Every workflow README should include:

- sample command;
- full or cached validation command;
- row count, date range, and universe size;
- base positive rate;
- AUC, hit rate, average forward return, or another suitable metric;
- latest prediction date;
- whether latest prediction rows are labeled;
- known test command.

Minimum automated tests:

- label construction edge case;
- no-lookahead or latest-tail behavior;
- dashboard grouping/classification;
- CLI argument forwarding for new public commands.

## 9. Naming Contract

Use current EDP naming:

- probability flow directions: `UPWARD`, `DOWNWARD`, `STABLE`;
- public Python API truth source: `src/python/__init__.py`;
- research command entrypoint: `src/python/edp_cli.py`;
- workflow folders: lowercase words joined by underscores.

Avoid stale names such as `SPAF` in new code or docs unless documenting history.

## 10. Documentation Template

Each `research/<workflow>/README.md` should contain:

```markdown
# <Workflow Name>

## Research Question

P(...)

## Label

...

## Data Boundary

...

## Build

...

## Rank

...

## Daily Workflow

...

## Outputs

...

## Validation

...

## Known Limits

...
```

## 11. Acceptance Checklist

Before a workflow is considered EDP-compatible:

- [ ] The probability target is defined before the model.
- [ ] The label column is stable and documented.
- [ ] Data sources and cache files are documented.
- [ ] Latest-only fields are not used as historical features unless point-in-time.
- [ ] CLI commands are exposed through `edp`.
- [ ] Outputs include panel, rank/latest, dashboard, and summary where applicable.
- [ ] README includes validation metrics and known limits.
- [ ] Focused tests pass.
