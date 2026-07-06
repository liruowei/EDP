from __future__ import annotations

import argparse
import sys

from .version import VERSION


def run_status(args: argparse.Namespace) -> int:
    repo_root = args.repo_root
    print(f"edp_version={VERSION}")
    print(f"repo_root={repo_root}")
    print(f"python={sys.executable}")
    print(f"pyproject={(repo_root / 'pyproject.toml').exists()}")
    print(f"research_dir={(repo_root / 'research').exists()}")
    print("workflows=theme,theme-stock,divergence,strategy,low-buy,data")
    for path in [
        repo_root / "data" / "theme_rotation" / "edp_daily_dashboard" / "dashboard.md",
        repo_root / "data" / "theme_stock_rotation" / "edp_theme_stock_dashboard" / "dashboard.md",
        repo_root / "data" / "divergence_turning_point" / "edp_divergence_dashboard" / "dashboard.md",
    ]:
        print(f"dashboard_exists[{path.relative_to(repo_root)}]={path.exists()}")
    strategy_config = repo_root / "research" / "edp_turning_strategy" / "config.json"
    strategy_output_root = repo_root / "data" / "edp_turning_strategy"
    low_buy_config = repo_root / "research" / "second_day_low_buy" / "config.json"
    low_buy_output_root = repo_root / "data" / "second_day_low_buy"
    print(f"strategy_config_exists={strategy_config.exists()}")
    print(f"strategy_output_root_exists={strategy_output_root.exists()}")
    print(f"low_buy_config_exists={low_buy_config.exists()}")
    print(f"low_buy_output_root_exists={low_buy_output_root.exists()}")
    print("menu_hint=edp menu")
    return 0


def run_menu(args: argparse.Namespace) -> int:
    repo_root = args.repo_root
    print("EDP 工作流菜单")
    print(f"repo_root={repo_root}")
    print("")
    print("一键日常入口：")
    print("  edp theme daily                         # 题材轮动每日看板")
    print("  edp theme-stock daily")
    print("                                          # 题材内部个股排名")
    print("  edp divergence daily                    # 分歧转向点看板")
    print("  edp divergence intraday                 # 盘中循环刷新")
    print("  edp strategy backtest                   # 分歧转向策略回测")
    print("  edp data update")
    print("                                          # 补齐 EDP DuckDB 未复权日线")
    print("  edp data update-factors")
    print("                                          # 更新 EDP DuckDB 复权因子")
    print("  edp low-buy daily                       # 次日低吸候选")
    print("  edp low-buy monitor                     # 全市场低吸信号监控")
    print("")
    print("可组合研究步骤：")
    print("  edp <area> build                        # 构建特征/标签面板")
    print("  edp <area> rank                         # 生成概率排名")
    print("  edp <area> latest-breadth               # 叠加当前宽度/热度确认")
    print("  edp <area> dashboard                    # 生成看板")
    print("  edp strategy backtest                   # 运行策略层回测")
    print("  edp data update")
    print("                                          # 只更新未复权行情仓库，不跑选股")
    print("  edp data update-factors")
    print("                                          # 单独更新复权因子")
    print("  edp low-buy backtest                    # 回测次日低吸策略")
    print("  edp low-buy full-backtest               # 全市场样本外回测")
    print("  edp low-buy monitor                     # 监控当前低吸信号")
    print("  edp divergence intraday                 # 启动标准盘中监控")
    print("")
    print("辅助命令：")
    print("  edp status                              # 查看本地工作流状态")
    print("  edp theme-stock list-themes --keyword \"光刻\"")
    print("                                          # 查真实题材名称")
    print("  edp theme-stock diagnose-api --theme-name \"国家大基金持股\"")
    print("                                          # 诊断东方财富/AkShare 连通性")
    print("")
    print("不知道从哪里开始：")
    print("  1. 看题材强弱：edp theme daily")
    print("  2. 看题材内个股：先 edp theme-stock list-themes，再 edp theme-stock daily")
    print("  3. 看早期分歧转强：edp divergence daily")
    print("  4. 盘中确认候选：edp divergence intraday")
    print("  5. 验证策略效果：edp strategy backtest")
    print("  6. 找次日低吸：edp low-buy daily")
    print("  7. 实盘监控低吸信号：edp low-buy monitor")
    print("")
    print("文档：")
    print("  docs/research_index.md                  # 当前研究版图")
    print("  docs/research_contract.md               # 研究工作流约束")
    return 0
