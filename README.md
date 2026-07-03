# EDP — 期望域感知方法 V2.0（Expectation Domain Perception Method）

> **通用全域概率态势感知框架**
>
> *A Universal Domain-Aware Probabilistic Situation Awareness Framework*

[![CI](https://img.shields.io/github/actions/workflow/status/ai-nurmamat/EDP/ci.yml?branch=master&label=CI&logo=github)](https://github.com/ai-nurmamat/EDP/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/ai-nurmamat/EDP?include_prereleases&label=Release)](https://github.com/ai-nurmamat/EDP/releases)
[![Python](https://img.shields.io/pypi/pyversions/edp-framework)](https://pypi.org/project/edp-framework/)
[![License: MIT](https://img.shields.io/github/license/ai-nurmamat/EDP?color=blue)](https://github.com/ai-nurmamat/EDP/blob/master/LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-77%25-brightgreen)](https://github.com/ai-nurmamat/EDP/actions/workflows/ci.yml)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://docs.astral.sh/ruff/)
[![Typed: mypy strict](https://img.shields.io/badge/typed-mypy%20strict-2a6db0.svg)](http://mypy-lang.org/)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-FE5196.svg)](https://conventionalcommits.org)
[![Last commit](https://img.shields.io/github/last-commit/ai-nurmamat/EDP)](https://github.com/ai-nurmamat/EDP/commits/master)

**版本: 2.0** | **许可: MIT** | **Python 3.10+**

---

## 目录 Table of Contents

- [风险警示](#-严重风险警示-)
- [1. 概述 Overview](#1-概述-overview)
- [2. 七层堆叠式架构](#2-七层堆叠式架构-seven-layer-architecture)
- [3. 快速开始 Quick Start](#3-快速开始-quick-start)
- [4. 多种使用入口（MCP / Python API / Agent Skills / CLI）](#4-多种使用入口-entry-points)
- [5. 项目结构](#5-项目结构-project-structure)
- [6. 从 V1 升级到 V2.0](#6-从-v1-升级到-v20)
- [7. 学术引用与关联项目](#7-学术引用与关联项目-references--related-work)
- [社区文件](#社区文件-community-files)
- [附录 A. 数学基础（历史文档）](#附录-a-数学基础-mathematical-foundations历史文档)
- [附录 B. 核心引擎（历史文档）](#附录-b-核心引擎-core-engines历史文档)
- [附录 C. 实现规范（历史文档）](#附录-c-实现规范-implementation-specifications历史文档)
- [附录 D. 关键文献（历史文档）](#附录-d-关键文献-key-references历史文档)
- [附录 E. 使用范例（历史文档）](#附录-e-使用范例-usage-examples历史文档)
- [附录 F. 免责声明（历史文档）](#附录-f-免责声明-disclaimer历史文档)
- [附录 G. 许可证](#附录-g-许可证-license)

---

## ⚠️⚠️⚠️ 严重风险警示 ⚠️⚠️⚠️

```
本框架仅供学术研究与教育用途。它【不构成】任何投资建议、决策建议、
交易指导或财务规划建议。

1. 概率预测的不确定性：所有概率均为估计值，存在显著不确定性。
2. 历史不代表未来：历史概率模式【不保证】未来结果。"黑天鹅"事件
   不在模型覆盖范围内。
3. 资金损失风险：AllocationEngine 输出的分配方案可能导致全部本金
   损失。任何实际决策都存在重大风险。
4. 模型局限性：框架依赖输入数据质量、域适配器的正确实现、以及
   各引擎的数学假设。任何环节的错误都会传播到最终结果。
5. 非专业建议：本框架的输出【不是】持牌专业人士的建议。在
   做任何实际决策前，请咨询合格的专业人士。

使用者须自行承担一切决策风险。
```

---

## 1. 概述 Overview

**期望域感知方法（Expectation Domain Perception Method, EDP）** V2.0 是一个**通用的概率预测与决策框架**。

任何可以被分解为"若干可能结果 + 若干信息来源"的问题，都可以用 EDP 处理。

### 1.1 全域与近似全域

- **全域（Complete Domain）：** 所有可能结果互斥且穷举，知道其中一个概率即确定其余。
- **近似全域（Approximate Domain）：** 结果空间未完全穷举，但已覆盖绝大部分概率质量，剩余未覆盖部分可通过补集近似。

EDP 对两类问题使用同一套引擎，区别仅在于 EventGraph 的拓扑结构和归一化策略。

### 1.2 核心设计哲学

```
不要问"这是什么领域的问题"。
要问"有多少个信息来源，多少个可能结果，它们之间是什么关系"。
```

---

## 2. 七层堆叠式架构 Seven-Layer Architecture

EDP V2.0 在六层架构之上新增 **L7 保形预测层**，引入 2025 年概率预测
领域最重要的进展——有限样本、分布无关的覆盖率保证，并融合在线贝叶斯
堆叠、Hyvärinen score、模型多样性等前沿方法。

```
┌──────────────────────────────────────────────────────────────────────┐
│                    EDP V2.0 — 七层堆叠式架构                          │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Layer 7: 保形预测层 ★ 2025 前沿                                │  │
│  │  Split Conformal · ACI（分布漂移鲁棒）· AgACI · 有限样本覆盖率  │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 6: 回测与校准层                        │  │
│  │  Brier Score · Log Score · Hyvärinen Score · CRPS · 校准曲线    │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 5: 资源分配层                          │  │
│  │  Kelly Criterion · Markowitz · 三原则 · 风险分层 · 分数Kelly     │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 4: 全域感知层                          │  │
│  │  线性池 · 对数优比池 · 贝叶斯累积 · 共识 · 异常 · 模型多样性     │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 3: 流向分析层                          │  │
│  │  概率流向 · 动量 · 速度/加速度 · 倍增评分 · 级联检测            │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 2: 推断引擎层                          │  │
│  │  Beta-Binomial · Glicko-2 · 在线贝叶斯堆叠(Soft-Bayes) · ML-Poly│  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 1: 概率提取层                          │  │
│  │  Shin归一化 · 比例归一化 · 信心度映射 · 连续→离散               │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 0: 数据抽象层                          │  │
│  │  Outcome · Quote · Evidence(定向) · Snapshot · EventGraph       │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 融合的 2025–2026 前沿方法

| 方法 | 所在层 | 来源 | 价值 |
|------|--------|------|------|
| **Conformal Prediction (ACI/AgACI)** | L7 | Zaffran et al. 2022; Gibbs & Candès 2021 | 有限样本覆盖率保证，分布漂移鲁棒 |
| **Online Bayesian Stacking** | L2 | arXiv 2505.15638 (2025) | log-score 最优组合，regret bound |
| **Hyvärinen Score** | L6 | Hyvärinen 2005; Ehm & Gneiting 2012 | 不依赖归一化常数的 proper scoring |
| **Model Diversity (DTVW)** | L4 | arXiv 2508.07136 (2025) | 冗余惩罚，有效来源数估计 |
| **定向证据 log-odds 更新** | L0/L4 | 本框架 | 证据指向具体结果，避免概率被拉平 |

---

## 3. 快速开始 Quick Start

```python
from edp import EDP, GenericDomain, Outcome, Evidence

# 1. 定义问题域（任意"结果+信号"问题）
domain = GenericDomain([
    Outcome("rain", "下雨"),
    Outcome("no_rain", "不下雨"),
])

# 2. 初始化 EDP
edp = EDP(domain)

# 3. 传入信息来源，一键分析
result = edp.analyze(
    evidence=[
        Evidence("weather_model", "model", {"probability": 0.72}, confidence=0.8),
        Evidence("satellite", "sensor", {"probability": 0.68}, confidence=0.9),
        Evidence("historical", "model", {"probability": 0.60}, confidence=0.5),
    ],
    budget=1000,
)

print(result["summary"])
# 最可能: rain (~68%) | 来源: 3 | 共识: 0.91 | 分配: ...
print(result["probabilities"])
# {"rain": 0.68, "no_rain": 0.32}
```

详见 `examples/python/basic_usage.py`。

---

## 4. 多种使用入口 Entry Points

EDP 的设计目标是**适应性极强（highly adaptive）**：同一套七层引擎，
可以通过多种入口被不同角色使用——AI 助手、Python 开发者、Agent 框架、
命令行脚本。所有入口共享同一份 `EDP` 核心实现，行为完全一致。

```
                 ┌─────────────────────────────────────┐
                 │      EDP 七层核心引擎 (src/python)    │
                 │  L0 数据 → L1 提取 → L2 推断 → L3 流向 │
                 │  L4 融合 → L5 分配 → L6 校准 → L7 保形 │
                 └──────────────┬──────────────────────┘
                                │
   ┌────────────┬───────────────┼───────────────┬─────────────┐
   ▼            ▼               ▼               ▼             ▼
 MCP Server  Python API    Agent Skills       CLI        Notebook
 (AI 助手)   (开发者)      (Agent 框架)      (脚本)      (研究)
```

### 4.1 MCP Server —— 给 AI 助手预测能力

[`mcp/server.py`](mcp/server.py) 把 EDP 暴露为 Model Context Protocol
服务器，任何 MCP 兼容客户端（Claude Desktop 等）即可调用六类工具：

| 工具 | 层 | 用途 |
|------|----|------|
| `analyze_situation` | L0–L7 | 一键全栈分析（域 + 证据 + 保形 + 分配） |
| `calculate_true_probability` | L1 | Shin 归一化提取真实概率 |
| `assess_situation` | L4 | 多源情报融合（线性/对数优比/贝叶斯） |
| `conformal_predict` | L7 | 保形预测集（有限样本覆盖率保证） |
| `online_aggregate` | L2 | 在线专家聚合（ML-Poly/EWA/Ridge/堆叠） |
| `evaluate_prediction` | L6 | 校准评分（Brier/Log/Hyvärinen） |

```bash
python mcp/server.py
```

详见 [`mcp/README.md`](mcp/README.md)。

### 4.2 Python API —— 嵌入你的应用

作为库直接 `import`，适合集成进数据管线、Web 后端、研究脚本：

```python
from edp import EDP, GenericDomain, Outcome, Evidence

domain = GenericDomain([Outcome("a", "结果A"), Outcome("b", "结果B")])
edp = EDP(domain)
result = edp.analyze(evidence=[...], budget=1000)
```

安装：`pip install edp-framework`（或开发模式 `pip install -e ".[dev]"`）。
所有公开符号见 [`src/python/__init__.py`](src/python/__init__.py) 的 `__all__`。

### 4.3 Agent Skills —— 给 Agent 框架封装为技能

EDP 的 `DomainAdapter` + `GenericDomain` 抽象使任意"结果 + 信号"问题都能被
统一建模，因此可被任意 Agent 框架封装为一个**可复用技能（Skill）**：

- 输入契约：`outcomes[]` + `evidence[]`（每个证据带 `source_type`、
  `probability`、可选 `outcome_id`、`confidence`）
- 输出契约：`probabilities` + `prediction_set` + `summary` + 可选 `allocation`
- 域无关：天气、融资轮次、赛事比分、故障诊断……同一接口

Agent 框架只需把上节 MCP 工具或 Python API 包一层 Skill 描述符即可。
推荐通过 MCP 入口接入（传输层无关、跨框架通用）。

### 4.4 CLI / 脚本 —— 一次性分析

无需长驻进程，直接用 Python 脚本或 Notebook 跑一次性分析：

```bash
python examples/python/basic_usage.py
```

研究场景参见 [`examples/notebooks/`](examples/notebooks/)（含
`startup_funding.ipynb`、`football_score.ipynb`）。

---

## 5. 项目结构 Project Structure

```
edp/
├── src/python/
│   ├── __init__.py           # 包导出
│   ├── core.py               # L0: Outcome/Quote/Evidence(定向)/Snapshot/EventGraph/DomainAdapter
│   ├── probability_engine.py  # L1-3: Shin/Bayesian/Flow/Glicko-2
│   ├── online_aggregator.py   # L2: ML-Poly/EWA/Ridge/在线贝叶斯堆叠
│   ├── flow_amplification.py  # L3: 倍增/BFS/级联
│   ├── domain_awareness.py    # L4: 融合/共识/异常/模型多样性
│   ├── allocation_engine.py   # L5: Kelly/Markowitz/三原则
│   ├── calibration.py         # L6: Brier/Log/Hyvärinen/CRPS/校准曲线
│   ├── conformal.py           # L7: Split Conformal/ACI/AgACI（2025 前沿）
│   └── edp.py                 # 顶层 EDP 接口
├── tests/python/
├── examples/python/           # basic_usage.py
├── examples/notebooks/        # startup_funding.ipynb / football_score.ipynb
├── mcp/server.py              # MCP Server（暴露 EDP 给 AI 助手）
├── docs/theory/references.md
├── CHANGELOG.md               # 变更记录
├── CONTRIBUTING.md            # 贡献指南
├── CODE_OF_CONDUCT.md         # 行为准则
└── SECURITY.md                # 安全策略
```

---

## 6. 从 V1 升级到 V2.0

V2.0 相对 V1（4.1）的重大变更：

| 变更项 | V1 (4.1) | V2.0 |
|--------|----------|------|
| 架构层数 | 5 层 | 7 层（新增校准层 L6 + 保形预测层 L7） |
| 顶层接口 | 无统一入口 | `EDP` 类一键分析 |
| 域适配 | 硬编码 | `DomainAdapter` + `GenericDomain` |
| 事件关系 | 固定 | `EventGraph`（链/完全连接/自定义） |
| 在线聚合 | 无 | `OnlineAggregator`（ML-Poly/EWA/Ridge/在线贝叶斯堆叠） |
| 校准 | 无 | `CalibrationEngine`（Brier分解/Log/Hyvärinen/校准曲线） |
| 保形预测 | 无 | `ConformalEngine`（Split/ACI/AgACI，有限样本覆盖率保证） |
| 定向证据 | 无 | `Evidence.outcome_id`（指向具体结果，避免概率拉平） |
| 风险警示 | 简单声明 | 每个模块顶部强化警示 + AllocationEngine 详细警示 |

V1 的 `flow_analyzer.py`、`scheme_designer.py` 已移除，功能分别合并到 `flow_amplification.py`、`allocation_engine.py`。

---

## 7. 学术引用与关联项目 References & Related Work

EDP 站在巨人的肩膀上。每一层都有明确的学术出处，详见
[`docs/theory/references.md`](docs/theory/references.md)。

### 7.1 各层理论基础（关联项目/文献）

| 层 | 方法 | 关联文献 |
|----|------|----------|
| L1 | Shin 归一化 | Shin (1992), *Economic Journal* 102(411) |
| L2 | Beta-Binomial 共轭 | Gelman et al. (2013), *BDA3* |
| L2 | Glicko-2 评级 | Glickman (2001), *J. Appl. Stat.* 28(6) |
| L2 | 在线贝叶斯堆叠 | Waxman et al. (2025), arXiv:2505.15638 |
| L3 | 时间序列动量 | Moskowitz et al. (2012), *JFE* 104(2) |
| L3 | 信息级联 | Banerjee (1992), *QJE* 107(3) |
| L4 | 线性/对数优比意见池 | Cooke (1991); Genest & Zidek (1986) |
| L4 | 模型多样性 (DTVW) | Luo et al. (2025), arXiv:2508.07136 |
| L5 | Kelly 准则 / Markowitz | Kelly (1956); Markowitz (1952) |
| L6 | Proper Scoring (Hyvärinen) | Hyvärinen (2005); Ehm & Gneiting (2012) |
| L7 | Conformal / ACI / AgACI | Gibbs & Candès (2021); Zaffran et al. (2022) |

> 学术准确性说明：EDP 代码实现的是 **Glicko-2**（含波动率 σ），故引用
> Glickman (2001)《Dynamic Paired Comparison Models with Stochastic
> Variances》。Glickman (1999) 描述的是无波动率的 Glicko-1，不适用。

### 7.2 引用本项目

如果你在学术工作中使用 EDP，请按 [`CITATION.cff`](CITATION.cff) 引用
（GitHub 会自动渲染 APA/BibTeX 导出按钮）。

```bibtex
@software{edp2026,
  author  = {{EDP Team}},
  title   = {{EDP: Expectation Domain Perception Method}},
  year    = {2026},
  version = {2.0.0},
  url     = {https://github.com/ai-nurmamat/EDP},
  license = {MIT}
}
```

---

## 社区文件 Community Files

| 文件 | 说明 |
|------|------|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 贡献指南（开发流程、规范、提交约定） |
| [`CHANGELOG.md`](CHANGELOG.md) | 变更记录（Keep a Changelog 格式） |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | 行为准则（Contributor Covenant 2.1） |
| [`SECURITY.md`](SECURITY.md) | 安全策略与漏洞报告流程 |
| [`CITATION.cff`](CITATION.cff) | 学术引用元数据 |
| [`.github/`](.github/) | Issue/PR 模板、CODEOWNERS、CI/Release/Stale 工作流 |

欢迎在 [Discussions](https://github.com/ai-nurmamat/EDP/discussions) 交流，
Bug 请提 [Issue](https://github.com/ai-nurmamat/EDP/issues)，
安全漏洞请按 [`SECURITY.md`](SECURITY.md) 私下报告。

---

*EDP V2.0 — 通用全域概率态势感知框架*
*任何可被分解为"结果 + 信号"的问题，都可以用它处理*
*仅供学术研究与教育用途*

---

## 附录 A. 数学基础 Mathematical Foundations（历史文档）

> 以下为 V1 时期保留的详细数学推导，供深入参考。日常使用请以上文 V2.0 七层架构为准。

---

### A.1 Shin 归一化方法 — 真实概率的提取

市场报价包含边际利润（"overround"），无法直接解释为概率。Shin（1992）提出的模型假设边际与"内幕交易者"的存在成比例，从而从报价中反解出"真实概率"。

**问题形式化**：给定 N 个结果的报价 *q₁, q₂, ..., qN*，其中 *qᵢ > 1* 为小数报价。

**隐含概率**：πᵢ = 1/qᵢ。市场边际 *overround* 为：

> Σᵢ₌₁ᴺ πᵢ - 1 > 0

**Shin 迭代法**求解真实概率 *p*：

> pᵢ^{(k+1)} = (πᵢ − zᵏ √pᵢᵏ) / (1 − zᵏ Σⱼ √pⱼᵏ)

其中 *z* 为内幕交易比例估计，迭代直至 |pᵢᵏ⁺¹ − pᵢᵏ| < ε。

**参考**：Shin, H.S. (1992). *Prices of State-Contingent Claims with Insider Traders*. Economic Journal, 102(411), 426-435.

### A.2 Beta-Binomial 共轭贝叶斯推断

对于 Bernoulli 试验，采用 Beta 分布作为共轭先验：

- **先验**：Beta(α₀, β₀)
- **观察**：在 *n* 次试验中获得 *k* 次成功
- **后验**：Beta(α₀ + k, β₀ + n − k)

**后验均值**：

> E[p | evidence] = (α₀ + k) / (α₀ + β₀ + n)

**95% 可信区间**采用正态近似：

> CI₉₅ = p̂ ± 1.96 × √(p̂(1 − p̂)/(n_eff + 1))

**参考**：Gelman, A., Carlin, J.B., Stern, H.S., & Rubin, D.B. (2013). *Bayesian Data Analysis*, 3rd ed. Chapman & Hall/CRC.

### A.3 Glicko-2 评级系统

对 Elo 系统的改进，引入评级偏差（RD）与波动率（σ），提供更稳健的动态实力建模。

**核心更新方程**（在 Glicko-2 尺度：μ, φ, σ）：

> E(μ, μⱼ, φⱼ) = 1 / (1 + exp(−g(φⱼ)(μ − μⱼ)))

> g(φ) = 1 / √(1 + 3φ²/π²)

> ν = [Σⱼ g(φⱼ)² E(1 − E)]⁻¹

> Δ = ν · Σⱼ g(φⱼ) (sⱼ − E)

其中 ν 为估计方差，Δ 为改进偏差。

**参考**：Glickman, M.E. (2001). *Dynamic Paired Comparison Models with Stochastic Variances*. Journal of Applied Statistics, 28(6), 673-689.（注：Glickman 1999 描述的是无波动率的 Glicko-1；EDP 实现含 σ，故引用 2001。）

### A.4 概率流向分析

**定义**（在时间 Δt 内）：

> Flowᵢ = pᵢ(t + Δt) − pᵢ(t)

**时间序列动量评分**（Moskowitz et al., 2012）：

> momentum_score = Σ_t w_t · flow_t, 其中 Σ_t w_t = 1

**速度与加速度**：

> vᵢ = d(Flowᵢ) / dt,  aᵢ = d²(Flowᵢ) / dt²

**显著性阈值**：|flow| < 0.5% 稳定；0.5%–2% 低显著；2%–5% 中显著；≥5% 高显著。

### A.5 流向倍增评分

对结果 *i* 的倍增评分综合四要素：

> AmpScoreᵢ = BaseFlowᵢ × DirConsistᵢ × (1 + GradientPosᵢ) × MarketMomentum

- **方向一致性** *DirConsistᵢ*：相邻结果流向与目标结果同向的比例
- **梯度位置** *GradientPosᵢ*：归一化概率水平——低概率结果具有更高倍增潜力
- **市场动量** *MarketMomentum*：全体结果的平均动量

### A.6 多源情报融合

采用**混合融合策略**——线性池与对数优比池的加权组合：

**线性意见池**（Cooke, 1991）：

> p_linear = Σᵢ wᵢ · pᵢ, 其中 Σᵢ wᵢ = 1

**对数优比意见池**（Genest & Zidek, 1986）：

> logit(p_logodds) = Σᵢ wᵢ · logit(pᵢ)

**混合估计**：

> p_fused = α · p_linear + (1 − α) · p_logodds,  α ∈ [0, 1]

**源权重**由三维构成：

> wᵢ = reliabilityᵢ × confidenceᵢ × temporal_decayᵢ

> temporal_decayᵢ = 2^(−Δtᵢ / t½)

**共识评分**（基于源估计的离散度）：

> Consensus = 1 − min(σ_observed / σ_max, 1.0)

其中 σ_max = 0.5 为 Bernoulli(p=0.5) 的理论最大标准差。

### A.7 Kelly 最优资本分配

Kelly 准则最大化对数财富的期望增长率：

> f* = (p · b − q) / b = (p(b + 1) − 1) / b

其中：*p* 为成功概率，*b* 为净赔率（小数报价 − 1），*q = 1 − p*。

**分数 Kelly**（本框架默认 quarter-Kelly, 即 1/4）：

> f = κ · f*,  κ ∈ (0, 1]

用于控制波动率，代价是降低期望增长速率。

**资本分配的三大原则**：
1. **信号对齐原则**：仅分配给具有正概率流向信号的结果
2. **非对称潜力原则**：要求赔率与概率乘积满足正期望条件
3. **风险分散原则**：分配集中度 cap ≤ 20%，并维持多样化比

---

## 附录 B. 核心引擎 Core Engines（历史文档）

### B.1 ProbabilityEngine — 概率分析引擎

| 功能模块 | 理论基础 | 输出 |
|---------|---------|------|
| 真实概率计算 | Shin 归一化 / 迭代法 | p_true, margin, CI |
| 条件概率推断 | 贝叶斯条件定义 | p(A \| B) |
| 贝叶斯更新 | Beta-Binomial 共轭模型 | posterior α, β, CI |
| 先验融合 | 对数池 / 线性池 | 组合后验 |
| Glicko-2 评级 | Glickman (2001) | μ, RD, σ |
| 流向分析 | 时间序列动量 | flow_velocity, acceleration |

### B.2 FlowAnalyzer — 流向倍增引擎

| 功能模块 | 理论基础 | 输出 |
|---------|---------|------|
| 基础流向 | 差分时间序列 | Δp, v, a |
| 方向一致性 | 邻接结构评分 | 0 – 1 一致性系数 |
| 梯度位置 | 概率空间逆映射 | 0 – 1 倍增潜力 |
| 市场动量 | 加权聚合动量 | aggregate_momentum |
| 级联风险 | 信息级联理论 | 风险等级标记 |

### B.3 DomainAwarenessEngine — 全域感知引擎

| 功能模块 | 理论基础 | 输出 |
|---------|---------|------|
| 情报预处理 | 源可靠性评级（STANAG 2511 改编） | w_i, 归一化权重 |
| 线性池融合 | Cooke (1991) 意见池 | p_linear |
| 对数优比融合 | Genest & Zidek (1986) | p_logodds |
| 贝叶斯累积 | Pearl (1988) 序贯更新 | 后验对数优比 |
| 共识分析 | 方差-离散度变换 | consensus_score |
| 异常检测 | Z-score 阈值法 | anomaly list |
| 级联检测 | 信息级联理论 Bikhchandani (1992) | potential_cascade 标记 |
| 态势评估 | 稳定性分类器 | aggregate_probability, confidence, status |

### B.4 AllocationEngine — 资源分配引擎

| 功能模块 | 理论基础 | 输出 |
|---------|---------|------|
| 合法性检验 | 三大分配原则 | valid / warning / invalid |
| Kelly 分配 | Kelly (1956) 信息率准则 | fraction, amount |
| 风险分层 | 概率-赔率映射 | conservative / balanced / aggressive / extreme |
| Markowitz 再平衡 | 集中度约束 + 多样化比 | 优化后分配 |
| 组合统计 | 期望价值 / 风险贡献 | portfolio_EV, diversification_ratio |

---

## 附录 C. 实现规范 Implementation Specifications（历史文档）

### C.1 技术栈

| 层面 | 技术 |
|-----|------|
| 编程语言 | Python 3.10+, TypeScript 5.0+ |
| 类型安全 | 完整类型标注 (dataclass, Enum) |
| 数值精度 | IEEE 754 double-precision |
| 收敛准则 | ε = 1e-10 (Shin 迭代) |
| 收敛上限 | 100 次迭代 |

### C.2 代码质量与验证

- **Linting**: 静态语法与风格检查
- **格式化**: 标准风格统一格式化
- **类型检查**: MyPy 静态类型验证
- **测试框架**: pytest (Python) / Jest (TypeScript)

---

## 附录 D. 关键文献 Key References（历史文档）

| 理论 / 方法 | 文献 |
|-----------|------|
| Shin 归一化 | Shin, H.S. (1992). *Prices of State-Contingent Claims with Insider Traders*. Economic Journal, 102(411), 426-435. |
| 贝叶斯推断 | Gelman, A., Carlin, J.B., Stern, H.S., & Rubin, D.B. (2013). *Bayesian Data Analysis*, 3rd ed. Chapman & Hall/CRC. |
| 时间序列动量 | Moskowitz, T.J., Ooi, Y.H., & Pedersen, L.H. (2012). *Time Series Momentum*. Journal of Financial Economics, 104(2), 228-250. |
| Glicko-2 评级 | Glickman, M.E. (2001). *Dynamic Paired Comparison Models with Stochastic Variances*. Journal of Applied Statistics, 28(6), 673-689. |
| Elo 评级系统 | Elo, A.E. (1978). *The Rating of Chessplayers, Past and Present*. Arco. |
| 信息级联 | Banerjee, A.V. (1992). *A Simple Model of Herd Behavior*. Quarterly Journal of Economics, 107(3), 797-817. |
| | Bikhchandani, S., Hirshleifer, D., & Welch, I. (1992). *A Theory of Fads, Fashion, Custom, and Cultural Change as Information Cascades*. JPE, 100(5), 992-1026. |
| 概率分布融合 | Genest, C., & Zidek, J.V. (1986). *Combining Probability Distributions: A Critique and an Annotated Bibliography*. Statistical Science, 1(1), 114-135. |
| 共识动力学 | DeGroot, M.H. (1974). *Reaching a Consensus*. JASA, 69(345), 118-121. |
| 专家不确定性 | Cooke, R.M. (1991). *Experts in Uncertainty*. Oxford University Press. |
| Kelly 准则 | Kelly, J.L. (1956). *A New Interpretation of Information Rate*. Bell System Technical Journal, 35(4), 917-926. |
| | MacLean, L.C., Thorp, E.O., & Ziemba, W.T. (2010). *The Kelly Capital Growth Investment Criterion*. World Scientific. |
| 组合理论 | Markowitz, H.M. (1952). *Portfolio Selection*. Journal of Finance, 7(1), 77-91. |
| 通用组合 | Cover, T.M. (1991). *Universal Portfolios*. Mathematical Finance, 1(1), 1-29. |
| 前景理论 | Kahneman, D., & Tversky, A. (1979). *Prospect Theory: An Analysis of Decision Under Risk*. Econometrica, 47(2), 263-291. |
| 贝叶斯网络 | Pearl, J. (1988). *Probabilistic Reasoning in Intelligent Systems*. Morgan Kaufmann. |
| 信息论 | Cover, T.M., & Thomas, J.A. (2006). *Elements of Information Theory*, 2nd ed. Wiley. |

---

## 附录 E. 使用范例 Usage Examples（历史文档）

### E.1 Python 接口示例

```python
from edp import (
    ProbabilityEngine,
    FlowAnalyzer,
    DomainAwarenessEngine,
    AllocationEngine,
)

# ── 初始化引擎 ──────────────────────────────────────
prob_engine = ProbabilityEngine()
flow_engine = FlowAnalyzer()
domain_engine = DomainAwarenessEngine()
alloc_engine = AllocationEngine()

# ── 1. 从市场报价计算真实概率 ──────────────────────
result = prob_engine.calculate_true_probability({
    "home": 1.50, "draw": 4.20, "away": 6.00
})

# 结果包含: true_probabilities, margin, confidence_interval, method

# ── 2. 概率流向分析（时间序列） ─────────────────────
flow_report = prob_engine.analyze_flow(
    initial_snapshot=snapshot_t0,
    latest_snapshot=snapshot_t1,
    historical_snapshots=history,
)

# 结果包含: flows (逐结果 flow / velocity / acceleration / significance),
#          aggregate_momentum, time_delta

# ── 3. 流向倍增评分 ─────────────────────────────────
amp_report = flow_engine.calculate_amplification(
    flow_report,
    gradient_map={"home": ["draw"], "away": ["draw"]},
    outcome_probs=result.true_probabilities,
)

# ── 4. 全域感知 · 多源情报融合 ──────────────────────
from edp import EvidenceSource, SourceReliability, EvidenceType

sources = [
    EvidenceSource(
        source_id="model_01",
        source_type=EvidenceType.ANALYTICAL,
        reliability=SourceReliability.B,  # usually reliable
        timestamp=datetime.now(),
        content={"probability": 0.62},
        confidence=0.80,
    ),
    EvidenceSource(
        source_id="market_quote",
        source_type=EvidenceType.OBSERVATIONAL,
        reliability=SourceReliability.A,  # completely reliable
        timestamp=datetime.now(),
        content={"probability": result.true_probabilities["home"]},
        confidence=0.95,
    ),
    # ... additional intelligence sources
]

assessment = domain_engine.assess_situation(
    sources,
    prior_probability=0.5,
    fusion_method="hybrid",
)

# 结果包含: aggregate_probability, confidence, consensus_score,
#          stability_status, anomalies, variance

# ── 5. 资源分配（Kelly + Markowitz） ─────────────────
from edp import AllocationLeg

candidates = [
    AllocationLeg(
        identifier="outcome_home",
        probability=assessment.aggregate_probability,
        odds=1.50,
        signal_score=flow_report.flows[0].momentum_score,
        confidence=assessment.confidence,
        flow_direction="upward",
    ),
    # ...
]

bundle = alloc_engine.generate_allocation(
    budget=1000.0,
    candidates=candidates,
)

bundle = alloc_engine.optimize_portfolio(
    bundle, target_diversification=0.6
)
```

### E.2 TypeScript 接口示例（LEGACY）

> 注：`src/js/` 为 V1 遗留实现，仅作参考。V2.0 权威实现为 Python，通过 MCP 暴露给所有语言。

```typescript
import {
  ProbabilityEngine,
  FlowAnalyzer,
} from 'edp-framework';

const engine = new ProbabilityEngine();

const result = engine.calculateTrueProbability({
  home: 1.50, draw: 4.20, away: 6.00
});
```

---

## 附录 F. 免责声明 Disclaimer（历史文档）

**本框架仅供学术研究与教育用途。**

- 本框架不构成任何投资建议或决策建议；
- 使用本框架进行的任何决策由用户自行承担责任；
- 作者不对使用本框架造成的任何损失负责；
- 请遵守所在地区的法律法规。

---

## 附录 G. 许可证 License

MIT License — 详见仓库根目录 *LICENSE* 文件。

---

*以结构化分析、严格概率论与全域认知提供学术研究支持——仅供学术研究用途。*

*© 2026 — For Academic Research and Educational Purposes Only.*
