# 次日低吸选股策略

约束文档：`docs/research_contract.md`

输出字段说明：`research/second_day_low_buy/OUTPUT_SCHEMA.md`

本研究把“强势股分歧后，第二个交易日低吸”的人工判断固化成可运行规则。它不预测开盘追涨，而是生成次日低吸区、深水区、止损线和修复确认线。

## 研究问题

```text
P(stock 在强势后首个大分歧的次日，触发低吸区后获得短线修复收益 | date T 已知信息)
```

## 入选逻辑

1. 前 8 个交易日有明显强势段：区间涨幅或单日大阳满足阈值。
2. 入选日出现大分歧：跌幅、振幅、换手、成交额同时满足阈值。
3. 收盘没有彻底破坏结构：仍接近 10 日线和前段强势区。
4. 次日只做低吸计划：价格回踩 `buy_low ~ buy_high` 且分时出现承接，才算触发。

## 买点逻辑

- `buy_low ~ buy_high`：首要低吸区，通常贴近当日低点和 38.2% 回撤。
- `deep_buy_low ~ deep_buy_high`：深水恐慌区，通常贴近 50% 回撤或 10 日线。
- `stop_price`：结构失效线。
- `reclaim_price`：修复确认线，次日能收回更强。

## 数据边界

全市场日线默认来自 EDP 自维护的 DuckDB 行情仓库。每日先补未复权日线：

```powershell
edp data update
```

再单独更新复权因子：

```powershell
edp data update-factors
```

两条命令的 `--end-date` 都可省略，默认使用今天；回补历史时再显式指定 `YYYYMMDD`。

- `stock_daily_raw`：未复权 OHLCV，由 AkShare 下载后写入。
- `stock_adj_factor`：复权因子，当前默认维护策略使用的 `qfq`。
- 策略读取时按 `config.full_market_oos.json` 的 `adjust` 派生复权价格。

`stock_daily_raw` 只落已完成交易日，不落今天的盘中行。若监控或日常读取区间包含今天，读取层会在内存中追加 AkShare 实时快照，再按复权因子派生 qfq/hfq 价格。这样原始行情和复权视图分开，也避免把盘中半日数据写成历史日线。

全市场股票池由共享 AkShare 元数据缓存导出，缓存目录为
`data/market_data/akshare_cache/stock_info/`，包含当前代码表、沪深退市表、
沪深代码表和更名表缓存。`full_market/universe.csv` 只是导出的当前股票池，
不是真相源；需要刷新 AkShare 元数据时使用 `--refresh-universe`。

行情可靠边界单独记录在 `market_data_sync_status`。日线状态按股票保存
`period=1d` 和 `reliable_data_time`：这个值是数据自身的最新可靠边界，
不是现实更新时间。常规更新可靠到最近历史交易日；15:03 之后若实时快照可用，
则可靠边界推进到当天这个交易日。

## 默认运行

```powershell
edp low-buy daily
```

回测模式：

```powershell
edp low-buy backtest
```

全市场样本外验证：

```powershell
edp low-buy full-backtest
```

实盘/盘后监控：

```powershell
edp low-buy monitor
```

监控默认读取 `research/second_day_low_buy/config.full_market_oos.json` 的 `monitor` 段，从共享 DuckDB 行情库生成当前交易日信号，并叠加“大反弹共性过滤器”：

- `优先入选`：前期涨幅、成交额、分歧振幅、收盘位置和低吸折价同时较强。
- `备选观察`：原始信号较强，但仍缺少一到两个关键确认。
- `原始信号/谨慎`：符合低吸模型，但不符合大反弹画像。

全市场和单票样本复现都不再维护 `{code}.csv` 二级日线缓存；动态补齐只通过 `edp data update` 写入共享 DuckDB。读取 `adjust=qfq` 时默认因子已经由日常 `edp data update-factors` 更新好；如果缺少对应因子则直接失败。股票池、AkShare 元数据和盘面快照这类辅助数据会保留独立 CSV 缓存。

也可以只验证指定股票：

```powershell
edp low-buy backtest --codes 002515,301182,300522,300401,300420
```

注意：上面的命令只是复现人工样本池，不代表全市场独立选股。样本复现配置单独放在：

```text
research/second_day_low_buy/config.sample_20260629.json
```

默认 `config.json` 不包含这些样本股，避免把已知案例当成生产候选池。

## 输出

```text
data/second_day_low_buy/{run_tag}/candidates.csv
data/second_day_low_buy/{run_tag}/signals_history.csv
data/second_day_low_buy/{run_tag}/report.md
data/second_day_low_buy/{run_tag}/backtest_events.csv
data/second_day_low_buy/{run_tag}/backtest_summary.csv
data/second_day_low_buy/monitor/{monitor_date}/monitor_signals.csv
data/second_day_low_buy/monitor/{monitor_date}/priority_signals.csv
data/second_day_low_buy/monitor/{monitor_date}/report.md
```

`candidates.csv` 只保存最新交易日候选；`signals_history.csv` 保存历史上所有入选记录。

## 已知限制

- 当前是日线级低吸计划，盘中承接仍需要分时确认。
- 回测用次日 OHLC 判断是否触发低吸区，不能还原真实排队成交。
- 全市场筛选依赖本地 DuckDB 行情和复权因子覆盖度；远程下载失败应先重新执行 `edp data update` 或 `edp data update-factors`。
- 使用 `--codes` 或样本配置得到的结果只能说明规则复现能力，不能作为泛化能力证据。
- 这是研究策略，不是交易指令。
