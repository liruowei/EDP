# 次日低吸研究输出字段说明

本文档说明 `research/second_day_low_buy` 相关 CSV 的表头含义。字段按“基础行情 -> 特征/买点 -> 回测/监控/画像”分层整理，方便查看 `data/second_day_low_buy/...` 下的输出。

约定：

- 价格字段默认单位为元。
- `amount` 为成交额，默认单位为元。
- `volume` 为成交量，按数据源原始口径保留。
- `pct_change`、`amplitude`、`turnover` 来自 EDP DuckDB 读时视图，通常是百分数口径，例如 `-5.56` 表示 `-5.56%`。
- `ret_1d`、`intraday_amplitude`、`runup_close_8d`、`close_vs_open` 等策略特征是小数口径，例如 `0.12` 表示 `12%`。
- `return`、`planned_return_cash_zero`、`avg_trade_return` 等收益率字段是小数口径。

## 文件索引

| 文件 | 说明 |
|---|---|
| `data/market_data/edp_market_data.duckdb::stock_daily_raw` | EDP 自维护未复权日线行情表。 |
| `data/market_data/edp_market_data.duckdb::stock_adj_factor` | EDP 自维护复权因子表，当前默认维护 `qfq`。 |
| `data/market_data/akshare_cache/stock_info/*.csv` | AkShare 当前代码、退市、代码表和更名表缓存。 |
| `full_market/universe.csv` | 由共享 AkShare 元数据缓存导出的当前全市场股票池。 |
| `cache/spot/stock_zh_a_spot_em_{date}.csv` | AkShare 盘面快照缓存，仅用于日常预筛股票池。 |
| `{run_tag}/candidates.csv` | `edp low-buy daily` 最新候选。 |
| `{run_tag}/signals_history.csv` | `edp low-buy daily/backtest` 历史入选信号。 |
| `{run_tag}/backtest_events.csv` | 单票候选池回测事件。 |
| `{run_tag}/backtest_summary.csv` | 单票候选池回测汇总。 |
| `full_market_oos/{run}/signals_all.csv` | 全市场所有原始低吸信号。 |
| `full_market_oos/{run}/signals_selected_topn.csv` | 全市场每日 TopN 信号。 |
| `full_market_oos/{run}/events_selected_topn.csv` | 全市场 TopN 回测事件。 |
| `full_market_oos/{run}/summary_by_split.csv` | 全市场样本内/样本外汇总。 |
| `full_market_oos/{run}/daily_portfolio.csv` | 全市场每日组合收益。 |
| `full_market_oos/{run}/download_failures.csv` | 行情读取失败明细。 |
| `full_market_oos/{run}/rebound_profile/*.csv` | 大反弹画像与条件扫描。 |
| `monitor/{date}/monitor_signals.csv` | 实盘/盘后监控全部信号。 |
| `monitor/{date}/priority_signals.csv` | 监控中的优先入选信号。 |

## 原始行情字段

### 统一日线字段

对应文件：从 `stock_daily_raw` 和 `stock_adj_factor` 派生的读时行情视图，以及信号文件中的行情基础列。

| 字段 | 含义 |
|---|---|
| `date` | 交易日期。 |
| `stock_code` | 六位股票代码。 |
| `stock_name` | 股票名称。 |
| `open` | 开盘价。 |
| `close` | 收盘价。 |
| `high` | 最高价。 |
| `low` | 最低价。 |
| `volume` | 成交量。 |
| `amount` | 成交额。 |
| `amplitude` | 数据源原始振幅，百分数口径。 |
| `pct_change` | 数据源原始涨跌幅，百分数口径。 |
| `change` | 涨跌额。 |
| `turnover` | 换手率，百分数口径。 |
| `ret_1d` | 当日涨跌幅，小数口径，通常由 `pct_change / 100` 得到。 |

## 策略特征字段

对应文件：`candidates.csv`、`signals_history.csv`、`signals_all.csv`、`signals_selected_topn.csv`、`monitor_signals.csv`。

| 字段 | 含义 |
|---|---|
| `ma5` | 5 日均线。 |
| `ma10` | 10 日均线。 |
| `ma20` | 20 日均线。 |
| `prev_close` | 前一交易日收盘价。 |
| `intraday_amplitude` | 日内振幅，小数口径，约等于 `(high - low) / low`。 |
| `close_vs_open` | 收盘相对开盘涨跌，小数口径，约等于 `close / open - 1`。 |
| `runup_close_8d` | 近 8 日收盘涨幅，小数口径。 |
| `max_gain_8d` | 近 8 日最大单日强度/涨幅特征，小数口径。 |
| `recent_high_10d` | 近 10 日最高价。 |
| `recent_low_10d` | 近 10 日最低价。 |
| `recent_low_8d` | 近 8 日最低价。 |
| `close_to_ma10` | 收盘价相对 10 日线距离，小数口径。 |
| `distance_to_ma5` | 收盘价相对 5 日线距离，小数口径。 |

## 买点计划字段

| 字段 | 含义 |
|---|---|
| `swing_low` | 计算低吸结构时使用的波段低点。 |
| `swing_high` | 计算低吸结构时使用的波段高点。 |
| `fib382` | 波段 38.2% 回撤参考价。 |
| `fib50` | 波段 50% 回撤参考价。 |
| `fib618` | 波段 61.8% 回撤参考价。 |
| `buy_low` | 首要低吸区下沿。 |
| `buy_high` | 首要低吸区上沿；回测里触发后按该价作为保守买入价。 |
| `deep_buy_low` | 深水低吸区下沿。 |
| `deep_buy_high` | 深水低吸区上沿。 |
| `stop_price` | 结构失效/止损参考价。 |
| `reclaim_price` | 修复确认价，通常为收盘价和 5 日线中的较高者。 |
| `signal_score` | 原始低吸信号分，越高表示越符合当前规则。 |
| `signal_state` | 信号状态，当前主要为 `next_day_low_buy_watch`。 |
| `rank_in_day` | 当日信号排名，`1` 表示当天最高分。 |

## 单票候选池回测字段

对应文件：`{run_tag}/backtest_events.csv`

| 字段 | 含义 |
|---|---|
| `signal_date` | 信号日。 |
| `entry_date` | 计划低吸日，通常为信号后第 1 个交易日。 |
| `exit_date` | 回测退出日。 |
| `entry_low` | 低吸日最低价。 |
| `entry_high` | 低吸日最高价。 |
| `entry_open` | 低吸日开盘价。 |
| `entry_close` | 低吸日收盘价。 |
| `touched` | 低吸日是否触达 `buy_low ~ buy_high`。 |
| `entry_price` | 回测买入价；触发时使用 `buy_high`。 |
| `exit_price` | 回测退出价；当前使用退出日收盘价。 |
| `return` | 单笔收益率，小数口径。 |

对应文件：`{run_tag}/backtest_summary.csv`

| 字段 | 含义 |
|---|---|
| `signals` | 回测信号数量。 |
| `triggered` | 触发低吸区的数量。 |
| `trigger_rate` | 触发率。 |
| `avg_return` | 触发交易平均收益。 |
| `median_return` | 触发交易收益中位数。 |
| `win_rate` | 触发交易胜率。 |
| `best_return` | 最好单笔收益。 |
| `worst_return` | 最差单笔收益。 |

## 全市场样本外回测字段

对应文件：`full_market_oos/{run}/events_selected_topn.csv`

| 字段 | 含义 |
|---|---|
| `rank_in_day` | 信号日在全市场入选信号中的排名。 |
| `planned_return_cash_zero` | 组合口径收益；未触发低吸时按 `0` 计，触发时等于单笔收益。 |

除上表外，其余字段与“单票候选池回测字段”一致。

对应文件：`full_market_oos/{run}/summary_by_split.csv`

| 字段 | 含义 |
|---|---|
| `split` | 样本区间，通常为 `all`、`in_sample`、`out_of_sample`。 |
| `signals` | 信号数量。 |
| `triggered` | 触发低吸区数量。 |
| `trigger_rate` | 触发率。 |
| `avg_trade_return` | 触发交易平均收益。 |
| `median_trade_return` | 触发交易收益中位数。 |
| `avg_planned_return_cash_zero` | 未触发按 0 计的计划平均收益。 |
| `win_rate` | 触发交易胜率。 |
| `daily_events` | 有信号的交易日数量。 |
| `daily_avg_return` | 日度组合平均收益。 |
| `daily_max_drawdown` | 日度组合最大回撤。 |

对应文件：`full_market_oos/{run}/daily_portfolio.csv`

| 字段 | 含义 |
|---|---|
| `signal_date` | 信号日。 |
| `selected` | 当日入选数量。 |
| `triggered` | 当日触发低吸数量。 |
| `portfolio_return_cash_zero` | 当日组合收益；未触发仓位按现金 0 收益处理。 |

## 监控字段

对应文件：`monitor/{date}/monitor_signals.csv`、`monitor/{date}/priority_signals.csv`

| 字段 | 含义 |
|---|---|
| `close_pos_10d` | 收盘在近 10 日高低区间中的位置，越接近 1 越靠近区间高位。 |
| `pullback_from_recent_high` | 收盘价相对近 10 日高点回撤，小数口径。 |
| `buy_high_discount_to_close` | `buy_high` 相对信号日收盘价的折价，小数口径。 |
| `monitor_runup_ok` | 是否满足监控层的前期涨幅条件。 |
| `monitor_amount_ok` | 是否满足监控层成交额条件。 |
| `monitor_strong_amount` | 是否满足更强成交额条件。 |
| `monitor_amplitude_ok` | 是否满足监控层分歧振幅条件。 |
| `monitor_extreme_amplitude` | 是否满足极强分歧振幅条件。 |
| `monitor_position_ok` | 是否满足收盘位置条件。 |
| `monitor_rank_ok` | 是否满足当日排名条件。 |
| `monitor_discount_ok` | 是否满足低吸价相对收盘价折价条件。 |
| `rebound_filter_score` | 大反弹共性过滤器得分。 |
| `monitor_level` | 监控分层：`优先入选`、`备选观察`、`原始信号/谨慎`。 |
| `monitor_level_order` | 监控分层排序值，数字越小优先级越高。 |

## 大反弹画像字段

对应文件：`rebound_profile/rebound_labeled_signals.csv`

| 字段 | 含义 |
|---|---|
| `t1_date`、`t2_date`、`t3_date` | 信号后第 1/2/3 个交易日。 |
| `t1_open`、`t1_high`、`t1_low`、`t1_close` | T+1 日 OHLC；T+2/T+3 同理。 |
| `t1_pct_change` | T+1 日涨跌幅，百分数口径；T+2/T+3 同理。 |
| `t1_touch_buy_zone` | T+1 是否触达 `buy_low ~ buy_high`；T+2/T+3 同理。 |
| `t1_high_ret_from_buy_high` | T+1 最高价相对 `buy_high` 的收益。 |
| `t1_close_ret_from_buy_high` | T+1 收盘价相对 `buy_high` 的收益。 |
| `max_high_ret_t1_t3` | T+1 到 T+3 最高价相对 `buy_high` 的最大收益。 |
| `max_close_ret_t1_t3` | T+1 到 T+3 收盘价相对 `buy_high` 的最大收益。 |
| `max_high_ret_t2_t3` | T+2 到 T+3 最高价相对 `buy_high` 的最大收益。 |
| `max_close_ret_t2_t3` | T+2 到 T+3 收盘价相对 `buy_high` 的最大收益。 |
| `t1_touched` | T+1 是否触发低吸区。 |
| `t1_big_rebound` | T+1 是否满足大反弹定义。 |
| `t2_t3_big_rebound` | T+2 到 T+3 是否满足大反弹定义。 |
| `big_rebound_1_3` | T+1 到 T+3 是否满足大反弹定义。 |
| `board` | 板块分类：主板、创业板、科创板。 |
| `split` | 样本划分：样本内或样本外。 |

对应文件：`rebound_profile/feature_summary_by_rebound_group.csv`

| 字段 | 含义 |
|---|---|
| `group` | 画像分组，例如大反弹组、未大反弹组。 |
| `feature` | 被统计的特征名。 |
| `n` | 样本数量。 |
| `mean` | 均值。 |
| `median` | 中位数。 |
| `p25` | 25% 分位数。 |
| `p75` | 75% 分位数。 |

对应文件：`rebound_profile/rebound_condition_scan.csv`

| 字段 | 含义 |
|---|---|
| `combo` | 条件组合，例如 `成交额>20亿 + 8日涨幅>50%`。 |
| `split` | 样本划分。 |
| `n` | 满足条件的样本数量。 |
| `big` | 满足大反弹定义的样本数量。 |
| `rate` | 大反弹概率。 |
| `t1_rate` | T+1 大反弹概率。 |
| `t23_rate` | T+2 到 T+3 大反弹概率。 |
| `avg_max_high` | 条件组内 T+1 到 T+3 最大冲高收益均值。 |

对应文件：`rebound_profile/rebound_lift_table.csv`

| 字段 | 含义 |
|---|---|
| `feature` | 分桶特征名。 |
| `bucket` | 分桶值。 |
| `n` | 分桶样本数。 |
| `big` | 分桶内大反弹样本数。 |
| `rate` | 分桶大反弹概率。 |
| `lift_vs_touched` | 相对全部触达低吸区样本的大反弹概率提升倍数。 |
| `avg_max_high` | 分桶内最大冲高收益均值。 |
| `avg_max_close` | 分桶内最大收盘收益均值。 |

对应文件：`rebound_profile/big_rebound_examples.csv`

该文件只保留大反弹样本，字段为信号特征、买点区间和 T+1/T+2/T+3 反弹表现的精简组合。

对应文件：`rebound_profile/selection_after_20260629_close.csv`

| 字段 | 含义 |
|---|---|
| `selection_level` | 盘后复盘分层：优先入选、备选观察、原始信号/谨慎。 |
| `amount_gt_10e` | 成交额是否大于 10 亿。 |
| `runup_gt_50` | 近 8 日涨幅是否大于 50%。 |
| `amp_gt_14` | 日内振幅是否大于 14%。 |
| `pos_gt_65` | 收盘位置是否在近 10 日区间 65% 以上。 |
| `discount_2p5_8` | 低吸区上沿相对收盘是否折价 2.5% 到 8%。 |

## 股票池和失败明细

对应文件：`full_market/universe.csv`、`full_market_oos/{run}/universe.csv`。这些文件由共享 AkShare 元数据缓存导出，不作为股票状态真相源。

| 字段 | 含义 |
|---|---|
| `stock_code` | 六位股票代码。 |
| `stock_name` | 股票名称。 |

对应文件：`download_failures.csv`

| 字段 | 含义 |
|---|---|
| `stock_code` | 下载失败股票代码。 |
| `stock_name` | 下载失败股票名称。 |
| `error` | 失败原因。 |
