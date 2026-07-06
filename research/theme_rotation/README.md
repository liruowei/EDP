# 题材轮动研究

约束文档：`docs/research_contract.md`

这是当前 EDP 的正式题材层工作流，用于横截面比较概念板块和行业板块，回答哪些题材更可能在短周期内进入强势组。

## 研究问题

```text
P(theme 在未来 H 个交易日进入强势题材组 | date T 已知信息)
```

默认预测窗口：

```text
H in {1, 3, 5}
```

## 标签

默认标签：

```text
label_top_20pct_{horizon}d = 1
if date T 上，题材未来 {horizon} 日收益位于同源题材横截面前 20%
else 0
```

基准样本：

- 同一 `theme_source`、同一日期下的全部可用题材；
- 默认实用数据源：`concept_ths`；
- 支持数据源：`concept_em`、`concept_ths`、`industry_em`、`industry_ths`。

## 配置

每日入口读取：

```text
research/theme_rotation/config.json
```

日常参数如 `theme_source`、`horizons`、`model`、`include_breadth`、缓存策略和输出目录都在配置文件里维护。底层 `build`、`rank`、`latest-breadth`、`dashboard` 命令仍保留参数，供研究拆解和验证使用。

## 数据边界

训练特征只使用 date T 当时可获得的题材指数历史数据。未来收益只作为标签列使用。每日工作流会通过 `--keep-unlabeled-tail` 保留最新无标签尾部，仅用于 live prediction。

同花顺最新宽度是当前确认层，只用于解释当天候选和生成看板；在补齐 point-in-time 宽度历史之前，不能作为历史训练特征。

远程数据缓存目录：

```text
data/theme_rotation/akshare_cache/
```

`latest-breadth` 会额外维护当天宽度确认层历史：

```text
data/theme_rotation/theme_rotation_breadth_snapshot_history.csv
```

东方财富概念接口可能断连。`concept_ths` 是 EM 概念列表不稳定时的优先实用替代源。

题材/行业指数仍由 AkShare 提供，并按本工作流自己的远程缓存边界维护。A 股个股日线不在本工作流里直接拉取；涉及个股日线的研究应复用 `edp data update` 维护的共享 DuckDB 行情仓库。

## 构建

构建小样本验证面板：

```powershell
edp theme build `
  --theme-source concept_ths `
  --max-themes 30 `
  --start-date 20240101 `
  --horizons 1,3,5 `
  --keep-unlabeled-tail `
  --output data\theme_rotation\theme_rotation_1_3_5d_concept_ths_sample.csv
```

常用变体：

```powershell
edp theme build `
  --theme-source concept_ths `
  --theme-filter "AI|机器人|半导体|新材料" `
  --horizons 1,3,5 `
  --output data\theme_rotation\theme_rotation_1_3_5d_selected.csv

edp theme build `
  --theme-source industry_ths `
  --horizons 1,3,5 `
  --output data\theme_rotation\theme_rotation_1_3_5d_industry_ths.csv
```

## 排名

运行单个预测窗口：

```powershell
edp theme rank `
  --input data\theme_rotation\theme_rotation_1_3_5d_concept_ths_sample.csv `
  --horizon 3 `
  --top-n 10 `
  --output data\theme_rotation\theme_rotation_concept_ths_3d_walk_forward_rank.csv `
  --latest-output data\theme_rotation\theme_rotation_concept_ths_3d_latest_rank.csv
```

EDP 概率流字段：

- `prob_strong_theme`：成为强势题材的概率。
- `prob_flow_pp`：概率变化，单位百分点。
- `prob_momentum_3d_pp`：3 日滚动概率流。
- `flow_direction`：upward / downward / stable。
- `signal_state`：强势、上升、退潮、等待等状态分类。

## 最新宽度

给最新 3 日排名叠加当前内部热度：

```powershell
edp theme latest-breadth `
  --rank-input data\theme_rotation\theme_rotation_concept_ths_3d_latest_rank.csv `
  --theme-source concept_ths `
  --top-n 30 `
  --output data\theme_rotation\theme_rotation_concept_ths_3d_latest_breadth.csv
```

该步骤会生成当前快照字段，例如 `up_ratio`、`board_change_pct`、`net_inflow_100m`、`amount_100m`、`leader_stock`、`breadth_score`、`prob_breadth_score`。

## 看板

生成 EDP 每日题材看板：

```powershell
edp theme dashboard `
  --rank-1d data\theme_rotation\theme_rotation_concept_ths_1d_live_rank.csv `
  --rank-3d data\theme_rotation\theme_rotation_concept_ths_3d_live_rank.csv `
  --rank-5d data\theme_rotation\theme_rotation_concept_ths_5d_live_rank.csv `
  --breadth-input data\theme_rotation\theme_rotation_concept_ths_3d_live_latest_breadth.csv `
  --output-dir data\theme_rotation\edp_daily_dashboard
```

稳定看板分组：

- `mainline_candidate`
- `launch_candidate`
- `crowded_short_term`
- `cooling_candidate`
- `watchlist`

## 每日工作流

运行完整实用流程：

```powershell
edp theme daily
```

每日入口按 `config.json` 执行。需要使用缓存、跳过宽度、调整窗口、模型或输出目录时，改配置文件，不改命令。

## 输出

默认每日输出：

```text
data/theme_rotation/theme_rotation_1_3_5d_concept_ths_live.csv
data/theme_rotation/theme_rotation_concept_ths_1d_live_rank.csv
data/theme_rotation/theme_rotation_concept_ths_3d_live_rank.csv
data/theme_rotation/theme_rotation_concept_ths_5d_live_rank.csv
data/theme_rotation/theme_rotation_concept_ths_3d_live_latest_breadth.csv
data/theme_rotation/edp_daily_dashboard/dashboard.csv
data/theme_rotation/edp_daily_dashboard/dashboard.md
data/theme_rotation/edp_daily_dashboard/summary.json
```

## 验证

首次本地 30 个同花顺概念样本：

| 窗口 | AUC | 基准正例率 | Top10 命中率 | Top10 平均未来收益 |
| --- | ---: | ---: | ---: | ---: |
| 1d | 0.5610 | 0.2333 | 0.2833 | 0.0009 |
| 3d | 0.5722 | 0.2333 | 0.2978 | 0.0036 |
| 5d | 0.5756 | 0.2333 | 0.2946 | 0.0052 |

在这个样本里，3 日和 5 日窗口比 1 日窗口更稳定。

## 测试

运行共享 Python 测试：

```powershell
$env:PYTHONPATH = "src\python"
python -m pytest tests\python -q
```

## 已知限制

- 题材质量过滤仍是第一版。
- 当前宽度是 latest-only，不是历史训练特征。
- 严格使用成分股历史前，需要 point-in-time 题材成分股数据。
- 这是排序研究基线，不是可直接部署的交易规则。
