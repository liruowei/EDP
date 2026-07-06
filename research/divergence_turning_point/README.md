# 分歧转向点研究

约束文档：`docs/research_contract.md`

这是当前 EDP 的正式分歧转向点工作流，用于寻找可能从分歧状态转向可见强势、并进入主升浪前段的题材。

## 研究问题

```text
P(theme 在未来 H 个交易日前处于主升浪前的分歧转向点 | date T 已知信息)
```

默认预测窗口：

```text
H = 10
```

## 标签

默认标签：

```text
label_divergence_turn_10d = 1
if:
  1. date T 上，题材未来 10 日收益位于全题材前 20%
  2. 未来 10 日最大有利波动至少达到 4%
  3. 当前 5 日收益排名尚未进入最热 30%
else 0
```

这个目标刻意聚焦主升浪之前的转向位置，而不是已经显著走强的后段题材。

## 配置

研究参数集中在：

```text
research/divergence_turning_point/config.json
```

日频和盘中入口都会读取这个文件。常用配置包括 `theme_source`、`theme_input`、`daily.horizon`、`daily.model`、`daily.include_breadth`、`daily.breadth_top_n`、`daily.dashboard_top_n`、`intraday.interval_seconds` 和 `intraday.sleep_seconds`。

## 数据边界

训练特征来自 date T 当时可获得的题材指数历史数据。未来收益和未来 MFE 只作为标签相关列使用。

上游题材行情当前来自题材轮动面板，主路径仍是 AkShare / 同花顺概念数据。
A 股日线统一复用 `edp data update` 维护的共享 DuckDB 行情仓库。

最新宽度是当前确认层；除非使用下面的 point-in-time 历史文件，否则不能作为历史训练特征：

```text
data/divergence_turning_point/divergence_turning_breadth_snapshot_history.csv
```

该历史文件按 `date + theme_name` 去重。同一天同题材重复运行时，会替换旧记录。

## 构建

基于已有题材轮动面板构建：

```powershell
edp divergence build `
  --input data\theme_rotation\theme_rotation_1_3_5d_concept_ths_live.csv `
  --horizon 10 `
  --keep-unlabeled-tail `
  --output data\divergence_turning_point\divergence_turning_10d_concept_ths_live.csv
```

也可以直接从缓存 / 拉取的同花顺概念历史构建：

```powershell
edp divergence build `
  --theme-source concept_ths `
  --start-date 20240101 `
  --max-themes 80 `
  --horizon 10 `
  --output data\divergence_turning_point\divergence_turning_10d_concept_ths.csv
```

关键特征组：

- `divergence_score`：价格仍安静或分歧，但量能和日内承接开始改善。
- `turn_visibility_score`：分歧通过排名、量能和均线收复变得可见。
- `ret_5d_rank_pct`：避免追逐已经拥挤的题材。
- `market_regime_score`、`market_regime_state`：同日题材宇宙环境。

## 排名

运行 walk-forward 排名：

```powershell
edp divergence rank `
  --input data\divergence_turning_point\divergence_turning_10d_concept_ths_live.csv `
  --horizon 10 `
  --initial-train-days 252 `
  --refit-every-days 5 `
  --top-n 30 `
  --output data\divergence_turning_point\divergence_turning_10d_concept_ths_walk_forward_rank.csv `
  --latest-output data\divergence_turning_point\divergence_turning_10d_concept_ths_latest_rank.csv `
  --summary-output data\divergence_turning_point\divergence_turning_10d_concept_ths_summary.json
```

默认情况下，`latest-output` 会写出最新交易日的全量候选；`--top-n` 只用于信号阈值、摘要统计和看板展示。

EDP 概率流字段：

- `prob_divergence_turn`：分歧转向点目标概率。
- `prob_flow_pp`：概率变化，单位百分点。
- `prob_momentum_3d_pp`：滚动概率流动量。
- `rank_probability`：横截面概率排名。
- `signal_state`：转向、观察、过热、退潮、等待等状态分类。

## 最新宽度

给最新排名叠加当前成分股宽度：

```powershell
edp divergence latest-breadth `
  --rank-input data\divergence_turning_point\divergence_turning_10d_concept_ths_latest_rank.csv `
  --theme-source concept_ths `
  --output data\divergence_turning_point\divergence_turning_10d_concept_ths_latest_breadth.csv
```

默认会对 rank 输入里的全部候选做当前宽度复核。

该步骤会生成确认字段，例如 `up_ratio`、`rank_strength`、`net_inflow_100m`、`constituent_breadth_score`、`turn_breadth_score`、`breadth_confirmation_state`。

## 看板

生成每日看板：

```powershell
edp divergence dashboard `
  --breadth-input data\divergence_turning_point\divergence_turning_10d_concept_ths_latest_breadth.csv `
  --summary-input data\divergence_turning_point\divergence_turning_10d_concept_ths_summary.json `
  --top-n 30 `
  --output-dir data\divergence_turning_point\edp_divergence_dashboard
```

稳定看板分组：

- `confirmed_turning_candidate`
- `resilient_watchlist`
- `breadth_unconfirmed_watchlist`
- `breadth_improving_watchlist`
- `model_high_breadth_weak`
- `already_extended`
- `cooling_or_failed`
- `neutral_or_wait`

## 盘中监控

在已经生成 latest rank 之后，启动标准盘中监控：

```powershell
edp divergence intraday
```

仓库根目录也可以使用：

```powershell
.\divergence.cmd -Intraday
```

盘中模式默认使用配置里的最新全量候选和刷新间隔，直到手动按 `Ctrl+C` 停止。该入口不再暴露 dry-run、数量限制、输出路径、跳过看板等调试参数，避免日常维护分叉。

盘中模式会输出：

```text
data/divergence_turning_point/divergence_turning_intraday_latest.csv
data/divergence_turning_point/divergence_turning_intraday_snapshot_history.csv
data/divergence_turning_point/edp_intraday_dashboard/dashboard.md
```

和每日 `latest-breadth` 不同，盘中历史按 `snapshot_at + theme_name` 保留多轮快照，不会覆盖同一天的旧记录。盘中字段包括 `board_change_delta_pct`、`up_ratio_delta`、`net_inflow_delta_100m`、`turn_breadth_delta` 和 `intraday_state`，用于区分 `intraday_confirming`、`intraday_recovering`、`intraday_fading` 等状态。

## 每日工作流

运行完整流程：

```powershell
edp divergence daily
```

默认每日工作流会按 `config.json` 输出全量 latest rank，并对全部 latest 候选做宽度复核。需要跳过当前宽度、改变模型、调整窗口或看板数量时，改配置文件，不改命令。

仓库也保留 Windows 辅助脚本：

```powershell
.\divergence.cmd
.\divergence.cmd -Intraday
.\divergence.cmd -Open
```

## 输出

默认每日输出：

```text
data/divergence_turning_point/divergence_turning_10d_concept_ths_live.csv
data/divergence_turning_point/divergence_turning_10d_concept_ths_walk_forward_rank.csv
data/divergence_turning_point/divergence_turning_10d_concept_ths_latest_rank.csv
data/divergence_turning_point/divergence_turning_10d_concept_ths_summary.json
data/divergence_turning_point/divergence_turning_10d_concept_ths_latest_breadth.csv
data/divergence_turning_point/divergence_turning_breadth_snapshot_history.csv
data/divergence_turning_point/edp_divergence_dashboard/dashboard.csv
data/divergence_turning_point/edp_divergence_dashboard/dashboard.md
data/divergence_turning_point/edp_divergence_dashboard/summary.json
```

## 验证

351 个同花顺概念题材的完整缓存验证：

| 指标 | 值 |
| --- | ---: |
| 行数 | 108,810 |
| Walk-forward 日期数 | 310 |
| 基准正例率 | 8.89% |
| AUC | 0.6842 |
| Top30 命中率 | 16.90% |
| Top30 平均未来 10 日收益 | 0.76% |

最新 live prediction：

```text
latest_prediction_date = 2026-06-18
market_regime_state = mixed
market_regime_score = 0.5617
latest_prediction_is_labeled = false
```

30 个题材小样本：

| 指标 | 值 |
| --- | ---: |
| 行数 | 11,310 |
| Walk-forward 日期数 | 377 |
| 基准正例率 | 10.09% |
| AUC | 0.6909 |
| Top10 命中率 | 16.02% |
| Top10 平均未来 10 日收益 | 0.84% |

## 测试

聚焦回归测试覆盖未来 runup 标签、市场环境分类、point-in-time 宽度历史去重，以及看板分组文件清理：

```powershell
$env:PYTHONPATH = "src\python"
python -m pytest tests\python\test_divergence_turning_point.py -q
```

## 已知限制

- 最新宽度只是确认层；除非使用 point-in-time 历史，否则不是训练特征。
- 当前候选是 watchlist 状态，不是交易指令。
- 该流程仍是研究基线。
- 下一步稳健升级需要积累更多日期的 point-in-time 成分股宽度历史。
