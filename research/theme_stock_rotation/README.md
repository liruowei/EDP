# 题材内部个股排名研究

约束文档：`docs/research_contract.md`

这是当前 EDP 的正式题材个股工作流，用于在一个或多个活跃题材、概念或行业内部，对成分股做相对强弱概率排名。

## 研究问题

```text
P(stock 在未来 H 个交易日进入所属题材成分股前 X% | date T 已知信息)
P(stock 在未来 H 个交易日跑赢所属题材指数 | date T 已知信息)
```

默认预测窗口：

```text
H in {1, 3, 5}
```

## 标签

支持两个目标：

```text
target = top
label_top_{top_pct}pct_in_theme_{horizon}d = 1
if date T 上，个股未来收益位于同题材成分股前 top_pct%
else 0
```

```text
target = outperform
label_outperform_theme_{horizon}d = 1
if 个股未来收益 - 题材指数未来收益 > 0
else 0
```

基准样本：

- 同一个 `theme_name`；
- live 工作流保存的同一份快照成分股；
- 默认 `top_pct = 20`。

## 配置

每日入口读取：

```text
research/theme_stock_rotation/config.json
```

日常参数如 `theme_source`、`theme_names`、`target`、`top_pct`、`model`、远程请求节流、缓存策略和输出目录都在配置文件里维护。底层 `build`、`rank`、`dashboard` 命令仍保留参数，供研究拆解和验证使用。

## 数据边界

当前版本使用 AkShare 返回的当前成分股，并保存成分股快照。它适合日常 live 排名和复盘，但在积累足够每日成分股快照之前，不是严格 point-in-time 历史回测。

当前成分股快照：

```text
data/theme_stock_rotation/theme_stock_membership_snapshot.csv
```

题材名称到东方财富板块代码的缓存：

```text
data/theme_stock_rotation/theme_code_cache.csv
```

远程数据和历史缓存：

```text
data/theme_stock_rotation/akshare_cache/
```

其中名称列表缓存位于 `akshare_cache/theme_names/`，成分股和题材/行业指数历史也在该目录下按来源拆分缓存。`concept_em` 的题材名称解析最终依赖东方财富 `push2` 概念列表接口。如果该接口断连，优先用 `edp theme-stock list-themes` 查 `concept_ths` 真实名称，或在已知 EM 板块代码时传入 `--theme-code-map` / `--theme-code-map-file`。

A 股个股日线统一读取 `edp data update` / `edp data update-factors` 维护的共享 DuckDB 行情仓库；本工作流不再维护个股日线 CSV。AkShare 只负责当前成分股、题材/行业指数、题材名称等辅助数据，并按上述缓存目录复用。

## 构建

构建 live 题材个股面板：

```powershell
edp theme-stock build `
  --theme-source concept_ths `
  --theme-names "PCB概念,光刻机" `
  --horizons 1,3,5 `
  --keep-unlabeled-tail `
  --output data\theme_stock_rotation\theme_stock_1_3_5d_live.csv
```

低频远程请求模式：

```powershell
edp theme-stock build `
  --theme-names "国家大基金持股,PCB概念,光刻机" `
  --fetch-attempts 2 `
  --retry-base-seconds 10 `
  --remote-request-interval 3 `
  --em-hosts "79.push2.eastmoney.com" `
  --em-max-pages 20 `
  --sleep-seconds 1.5
```

已知板块代码时：

```powershell
edp theme-stock build `
  --theme-names "国家大基金持股,PCB概念,光刻机" `
  --theme-code-map "国家大基金持股=BK1234"
```

## 排名

按窗口和目标生成个股排名：

```powershell
edp theme-stock rank `
  --input data\theme_stock_rotation\theme_stock_1_3_5d_live.csv `
  --horizon 3 `
  --target top `
  --top-pct 20 `
  --top-n 20 `
  --output data\theme_stock_rotation\theme_stock_3d_live_rank.csv `
  --latest-output data\theme_stock_rotation\theme_stock_3d_live_latest_rank.csv
```

EDP 概率流字段：

- `prob_theme_stock`：所选目标的概率。
- `prob_flow_pp`：概率变化，单位百分点。
- `prob_momentum_3d_pp`：滚动概率流动量。
- `rank_in_theme_probability`：题材内部概率排名。
- `signal_state`：龙头、上升、走弱、等待等状态分类。

## 看板

生成题材个股看板：

```powershell
edp theme-stock dashboard `
  --rank-1d data\theme_stock_rotation\theme_stock_1d_live_rank.csv `
  --rank-3d data\theme_stock_rotation\theme_stock_3d_live_rank.csv `
  --rank-5d data\theme_stock_rotation\theme_stock_5d_live_rank.csv `
  --output-dir data\theme_stock_rotation\edp_theme_stock_dashboard
```

稳定看板分组：

- `leader_candidate`
- `launch_candidate`
- `catchup_candidate`
- `crowded_leader`
- `cooling_stock`

## 每日工作流

运行配置中的一个或多个题材：

```powershell
edp theme-stock daily
```

每日入口按 `config.json` 执行。需要修改题材名称、缓存策略、目标、模型、节流参数或输出目录时，改配置文件，不改命令。

查询真实题材名称：

```powershell
edp theme-stock list-themes `
  --theme-source concept_ths `
  --keyword "光刻"
```

诊断东方财富 / AkShare 连通性：

```powershell
edp theme-stock diagnose-api `
  --theme-name "国家大基金持股" `
  --request-interval 3 `
  --max-pages 10 `
  --skip-akshare
```

## 输出

默认每日输出：

```text
data/theme_stock_rotation/theme_stock_membership_snapshot.csv
data/theme_stock_rotation/theme_stock_1_3_5d_live.csv
data/theme_stock_rotation/theme_stock_1d_live_rank.csv
data/theme_stock_rotation/theme_stock_3d_live_rank.csv
data/theme_stock_rotation/theme_stock_5d_live_rank.csv
data/theme_stock_rotation/edp_theme_stock_dashboard/dashboard.csv
data/theme_stock_rotation/edp_theme_stock_dashboard/dashboard.md
data/theme_stock_rotation/edp_theme_stock_dashboard/summary.json
```

## 验证

当前验证重点是工作流和数据边界，而不是严格历史绩效证明：

- daily 命令能产出面板、1/3/5 日排名和看板。
- 成分股快照已保存，为后续 point-in-time 验证做准备。
- EM 概念解析不稳定时，`concept_ths` 是优先实用替代源。
- `theme_code_cache.csv` 会复用成功解析过的 EM 板块代码，避免反复扫描概念列表。

## 测试

运行共享 Python 测试：

```powershell
$env:PYTHONPATH = "src\python"
python -m pytest tests\python -q
```

## 已知限制

- 当前成分股不等于历史成分股。
- 在积累 point-in-time 成分股快照之前，本工作流不是严格历史回测。
- EM 和 AkShare 兜底路径可能共享同类 `push2` 上游失败。
- 这是排序研究基线，不是可直接部署的交易规则。
