# EDP Research Index

This index is the current convergence map for all research workflows.
New work should start from `docs/research_contract.md` and then choose one of
the active workflow shapes below.

## Active Workflows

| Area | Folder | CLI | Primary Target | Status |
| --- | --- | --- | --- | --- |
| Theme rotation | `research/theme_rotation/` | `edp theme ...` | `P(theme enters top 20% over H days)` | active |
| Theme-stock ranking | `research/theme_stock_rotation/` | `edp theme-stock ...` | `P(stock is top/outperforms inside active theme over H days)` | active |
| Divergence turning point | `research/divergence_turning_point/` | `edp divergence ...` | `P(theme is at a pre-main-wave turning point over 10 days)` | active |
| EDP turning strategy | `research/edp_turning_strategy/` | `edp strategy backtest` | `Theme-index strategy return/excess return after divergence-turning signals` | active |
| Second-day low-buy | `research/second_day_low_buy/` | `edp low-buy ...` | `P(stock rebounds after next-day low-buy zone following strong-stock divergence)` | active |
| Market data warehouse | `research/market_data/` | `edp data update` / `edp data update-factors` | Maintain unadjusted A-share OHLCV and separately refreshed adjustment factors in DuckDB | active |

## Standard Command Shape

Use the same mental model across active workflows:

```powershell
edp <area> daily
edp <area> build
edp <area> rank
edp <area> latest-breadth
edp <area> dashboard
edp divergence intraday
edp strategy backtest
edp data update
edp data update-factors
edp low-buy daily
```

`latest-breadth` is required only when the workflow has a current confirmation
layer. If a workflow has no such layer, its README must say so.

`divergence intraday` reuses the latest model rank and refreshes current breadth
snapshots repeatedly. It is intentionally scoped to the divergence workflow
because that workflow already separates model probability from live confirmation.

`strategy backtest` is the strategy layer for the divergence-turning model. It
does not rebuild labels or ranks; it consumes point-in-time walk-forward ranks
and theme-index panels, then writes backtest events, summaries, and reports.

`low-buy daily` is the stock execution research layer for strong-stock
divergence. It screens or validates a stock pool, writes next-day low-buy zones,
and can backtest whether those zones were touched and repaired.

`data update` is the shared A-share daily OHLCV layer. It uses AkShare only as
the remote data provider and writes unadjusted prices to EDP-owned
`stock_daily_raw`. `data update-factors` separately refreshes adjustment factors
in `stock_adj_factor`. Strategy workflows should consume this warehouse instead
of owning another historical daily cache. Both commands default `--end-date` to
today when the flag is omitted.
Adjustment-factor refreshes replace each stock/factor-type series instead of
appending date increments, because factor histories can be rebased.

The update commands derive their stock universe from the shared AkShare metadata
cache under `data/market_data/akshare_cache/stock_info/`: current code/name,
Shanghai/Shenzhen delist tables, listing code tables, and the cached Shenzhen
name-change table. Workflow `universe.csv` files are regenerated exports of this
cache.

`stock_daily_raw` is intentionally historical-only: today's live row is not
persisted. When a strategy reads through today, the market-data store appends an
in-memory AkShare spot snapshot and then derives adjusted prices at read time.
The companion `market_data_sync_status` table records the reliable boundary per
stock and period in data time, so strategies can distinguish "raw rows
persisted through yesterday" from "today's data boundary is reliable after the
15:03 close check."

AkShare data that is not individual A-share daily OHLCV stays inside an explicit
cache boundary: shared market metadata under `data/market_data/akshare_cache/`,
plus workflow-local caches for theme/industry lists and histories, constituent
snapshots, spot snapshots, and latest breadth histories.

## Development Rule

Do not add a new research folder until these are written:

- `Research Question`
- `Label`
- `Data Boundary`
- `CLI`
- `Outputs`
- `Validation`
- `Known Limits`

If a new idea is a variant of an active workflow, add it as an option, target,
or documented mode under that workflow before creating another folder.

Daily workflow and backtest defaults belong in each research folder's config file, for
example `research/divergence_turning_point/config.json`. CLI commands should
start workflows; config files should carry research parameters.
