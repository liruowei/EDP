# EDP 转向策略研究

约束文档：`docs/research_contract.md`

本研究把 `divergence_turning_point` 的模型信号收敛成可回测的策略规则。当前版本先做题材指数层回测：每天在同花顺概念指数宇宙里选题材，持有固定交易日，再与全题材等权基准比较。

## 研究问题

```text
当 EDP 分歧转向模型提示某些题材进入转向候选池时，
使用概率、分歧位置、可见性、过热过滤和市场状态过滤，
能否在未来 N 个交易日获得相对全题材基准的超额收益？
```

## 当前边界

- 回测对象是题材指数，不是个股。
- 历史信号只使用当日已有的 walk-forward rank 和题材面板字段。
- 当前同花顺成分股宽度只用于实盘/盘中确认；历史回测暂不使用当前成分股宽度，避免未来函数。
- 行情输入继承上游分歧转向面板；A 股日线统一复用 `edp data update` 维护的共享 DuckDB 行情仓库。
- 个股执行层后续需要 point-in-time 成分股、个股历史面板和历史宽度确认后再纳入正式回测。

## 策略版本

- `model_top30`：纯模型概率前 30 里取前 5，作为基线。
- `edp_filtered`：模型候选池 + 非过热 + 非冷却 + 分歧/可见性综合分。
- `edp_risk_adaptive`：在 `edp_filtered` 基础上，弱市场阶段空仓或少交易。

## 默认运行

日常使用直接从仓库根目录运行：

```powershell
edp strategy backtest
```

默认参数在 `research/edp_turning_strategy/config.json`：

- 优先使用 `data/divergence_turning_point/validation/` 下最新的一组验证 rank/panel。
- 找不到验证快照时，退回 `data/divergence_turning_point/` 下的常规输出。
- 默认跑 3 日、5 日、10 日持有期。
- 默认输出到 `data/edp_turning_strategy/validation_{run_tag}/`。

## 单次拆解运行

如果要单独验证某个持有周期，可以直接调用底层脚本：

```powershell
C:\Users\37943\.conda\envs\smart-quant\python.exe research\edp_turning_strategy\backtest_edp_turning_strategy.py `
  --rank-input data\divergence_turning_point\validation\divergence_turning_10d_concept_ths_walk_forward_rank_20260629.csv `
  --panel-input data\divergence_turning_point\validation\divergence_turning_10d_concept_ths_live_20260629.csv `
  --holding-days 5 `
  --output-dir data\edp_turning_strategy\validation_20260629
```

## 输出

```text
data/edp_turning_strategy/.../events_5d.csv
data/edp_turning_strategy/.../summary_5d.csv
data/edp_turning_strategy/.../report_5d.md
data/edp_turning_strategy/.../meta_5d.json
```

`events` 保存每次调仓的入场日期、退出日期、组合收益、基准收益、超额收益和选中题材。`summary` 保存均值收益、胜率、超额胜率和最大回撤等指标。

## 下一步

1. 将 point-in-time 宽度历史积累到足够日期后，加入正式历史回测。
2. 为入选题材增加个股执行层：题材内成分股、个股强弱、成交额、盘中位置和风险过滤。
3. 增加交易成本、滑点、停牌/涨跌停约束。
4. 比较 3 日、5 日、10 日持有和每日滚动组合版本。
