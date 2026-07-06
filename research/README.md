# EDP 本地研究入口

这里维护本 fork 的研究工作流、行情数据维护方式和日常命令。根目录
`README.md` 尽量保持原仓库文档，不承载这些本地研究说明。

## 研究规范

新增或调整研究方向前，先对齐：

- `docs/research_contract.md`
- `docs/research_index.md`

每个研究方向应说明概率目标、标签、数据边界、CLI、输出、验证方式和已知限制。
日常参数放在各研究目录自己的 `config.json` 中，不放在根 README。

## 安装 CLI

```powershell
cd C:\Workerspace\SmartQuant\EDP
& C:\Users\37943\.conda\envs\smart-quant\python.exe -m pip install -e .
```

安装后使用 `edp` 命令。

## 每日数据维护

15:03 之后执行：

```powershell
edp data update --refresh-universe
edp data update-factors
```

`edp data update` 维护本地 DuckDB 未复权日线：

- 数据库：`data/market_data/edp_market_data.duckdb`
- 原始未复权日线表：`stock_daily_raw`
- 同步状态表：`market_data_sync_status`
- 默认 `--end-date` 为今天
- 如果请求到今天，历史日线落库自动收口到昨天
- 15:03 后实时快照可用时，日线可靠边界可推进到今天

`edp data update-factors` 单独维护复权因子：

- 表：`stock_adj_factor`
- 默认维护配置中的因子类型，通常是 `qfq`
- 因子不是按日期增量追加，而是按 `stock_code + factor_type` 全量刷新后替换

行情缓存、DuckDB、研究输出都在 `data/` 下，属于运行时数据，不进 Git。

## 常用研究命令

```powershell
edp theme daily
edp theme-stock daily
edp divergence daily
edp divergence intraday
edp strategy backtest
edp low-buy daily
edp status
```

可组合步骤：

```powershell
edp theme build
edp theme rank --horizon 3
edp theme latest-breadth
edp theme dashboard

edp theme-stock build --theme-source concept_ths --theme-names "PCB概念,光刻机"
edp theme-stock rank --horizon 3 --target top
edp theme-stock dashboard

edp divergence build
edp divergence rank --horizon 10
edp divergence latest-breadth
edp divergence dashboard

edp low-buy backtest --codes 002515,301182,300522,300401,300420
```

未安装 CLI 时也可以直接运行模块：

```powershell
$env:PYTHONPATH = "src\python"
& C:\Users\37943\.conda\envs\smart-quant\python.exe -m edp_cli theme daily
```

## 研究目录

| 方向 | 目录 | 入口 |
| --- | --- | --- |
| 题材轮动 | `research/theme_rotation/` | `edp theme ...` |
| 题材内个股 | `research/theme_stock_rotation/` | `edp theme-stock ...` |
| 分歧转向点 | `research/divergence_turning_point/` | `edp divergence ...` |
| 分歧转向策略 | `research/edp_turning_strategy/` | `edp strategy backtest` |
| 次日低吸 | `research/second_day_low_buy/` | `edp low-buy ...` |
| 行情数据仓库 | `research/market_data/` | `edp data ...` |
