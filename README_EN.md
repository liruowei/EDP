# EDP — Expectation Domain Perception Method V2.0

> **A Universal Domain-Aware Probabilistic Situation Awareness Framework**
>
> *通用全域概率态势感知框架*

[![CI](https://img.shields.io/github/actions/workflow/status/ai-nurmamat/EDP/ci.yml?branch=master&label=CI&logo=github)](https://github.com/ai-nurmamat/EDP/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/ai-nurmamat/EDP?include_prereleases&label=Release)](https://github.com/ai-nurmamat/EDP/releases)
[![Python](https://img.shields.io/pypi/pyversions/edp-framework)](https://pypi.org/project/edp-framework/)
[![License: MIT](https://img.shields.io/github/license/ai-nurmamat/EDP?color=blue)](https://github.com/ai-nurmamat/EDP/blob/master/LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-77%25-brightgreen)](https://github.com/ai-nurmamat/EDP/actions/workflows/ci.yml)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://docs.astral.sh/ruff/)
[![Typed: mypy strict](https://img.shields.io/badge/typed-mypy%20strict-2a6db0.svg)](http://mypy-lang.org/)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-FE5196.svg)](https://conventionalcommits.org)
[![Last commit](https://img.shields.io/github/last-commit/ai-nurmamat/EDP)](https://github.com/ai-nurmamat/EDP/commits/master)

**Version: 2.0** | **License: MIT** | **Python 3.10+**

> 🌐 This is the English README. For the authoritative Chinese version, see
> [README.md (中文)](README.md).

---

## Table of Contents

- [Risk Warning](#-risk-warning-)
- [1. Overview](#1-overview)
- [2. Seven-Layer Stacked Architecture](#2-seven-layer-stacked-architecture)
- [3. Quick Start](#3-quick-start)
- [4. Entry Points (MCP / Python API / Agent Skills / CLI)](#4-entry-points-mcp--python-api--agent-skills--cli)
- [5. Project Structure](#5-project-structure)
- [6. Upgrading from V1 to V2.0](#6-upgrading-from-v1-to-v20)
- [7. References & Related Work](#7-references--related-work)
- [Community Files](#community-files)
- [Appendix A. Mathematical Foundations (legacy)](#appendix-a-mathematical-foundations-legacy)
- [Appendix B. Core Engines (legacy)](#appendix-b-core-engines-legacy)
- [Appendix C. Implementation Specifications (legacy)](#appendix-c-implementation-specifications-legacy)
- [Appendix D. Key References (legacy)](#appendix-d-key-references-legacy)
- [Appendix E. Usage Examples (legacy)](#appendix-e-usage-examples-legacy)
- [Appendix F. Disclaimer (legacy)](#appendix-f-disclaimer-legacy)
- [Appendix G. License](#appendix-g-license)

---

## ⚠️⚠️⚠️ Risk Warning ⚠️⚠️⚠️

```
This framework is for ACADEMIC RESEARCH AND EDUCATIONAL PURPOSES ONLY.
It does NOT constitute any investment advice, decision-making advice,
trading guidance, or financial planning advice.

1. Uncertainty of probabilistic forecasts: All probabilities are
   estimates with significant uncertainty.
2. Past ≠ Future: Historical probability patterns do NOT guarantee
   future outcomes. "Black swan" events are outside the model's coverage.
3. Capital loss risk: AllocationEngine outputs may lead to total loss
   of principal. Any real decision carries substantial risk.
4. Model limitations: The framework depends on input data quality,
   correct domain-adapter implementation, and the mathematical
   assumptions of each engine. Errors in any layer propagate to results.
5. Not professional advice: This framework's output is NOT the advice of
   a licensed professional. Consult qualified professionals before
   making any real-world decisions.

Users bear full responsibility for their own decisions.
```

---

## 1. Overview

**Expectation Domain Perception Method (EDP)** V2.0 is a **general-purpose
probabilistic forecasting and decision framework**.

Any problem that can be decomposed into "a set of possible outcomes +
a set of information sources" can be handled by EDP.

### 1.1 Complete vs. Approximate Domains

- **Complete Domain:** All possible outcomes are mutually exclusive and
  collectively exhaustive — knowing one probability determines the rest.
- **Approximate Domain:** The outcome space is not fully enumerated but
  covers most of the probability mass; the uncovered remainder is handled
  via complement approximation.

EDP uses the same engine for both; the difference lies only in the
EventGraph topology and the normalization strategy.

### 1.2 Core Design Philosophy

```
Don't ask "what domain is this problem in?".
Ask "how many information sources, how many possible outcomes,
and how are they related?".
```

---

## 2. Seven-Layer Stacked Architecture

EDP V2.0 adds **Layer 7 (Conformal Prediction)** atop the original six,
introducing the most important advance in probabilistic forecasting of
2025 — finite-sample, distribution-free coverage guarantees — together
with online Bayesian stacking, the Hyvärinen score, and model-diversity
metrics.

```
┌──────────────────────────────────────────────────────────────────────┐
│                    EDP V2.0 — Seven-Layer Stacked Architecture        │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Layer 7: Conformal Prediction  ★ 2025 frontier                │  │
│  │  Split Conformal · ACI (distribution-shift robust) · AgACI     │  │
│  │  Finite-sample coverage guarantee                              │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 6: Backtesting & Calibration          │  │
│  │  Brier Score · Log Score · Hyvärinen Score · CRPS · Cal. curve │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 5: Resource Allocation                │  │
│  │  Kelly Criterion · Markowitz · Three Principles · Risk tiering │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 4: Domain Awareness                   │  │
│  │  Linear pool · Log-odds pool · Bayesian accumulation · Consensus│ │
│  │  Anomaly · Model diversity                                    │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 3: Flow Analysis                      │  │
│  │  Probability flow · Momentum · Velocity/Acceleration ·         │  │
│  │  Amplification scoring · Cascade detection                    │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 2: Inference Engines                  │  │
│  │  Beta-Binomial · Glicko-2 · Online Bayesian Stacking (Soft-Bayes)│ │
│  │  ML-Poly · EWA · Ridge                                        │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 1: Probability Extraction             │  │
│  │  Shin normalization · Proportional normalization ·             │  │
│  │  Confidence mapping · Continuous → Discrete                   │  │
│  ├────────────────────────────────────────────────────────────────┤  │
│  │                    Layer 0: Data Abstraction                   │  │
│  │  Outcome · Quote · Evidence (directed) · Snapshot · EventGraph│  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 2025–2026 Frontier Methods Integrated

| Method | Layer | Source | Value |
|--------|-------|--------|-------|
| **Conformal Prediction (ACI/AgACI)** | L7 | Zaffran et al. 2022; Gibbs & Candès 2021 | Finite-sample coverage guarantee, distribution-shift robust |
| **Online Bayesian Stacking** | L2 | arXiv 2505.15638 (2025) | Log-score-optimal combination, regret bound |
| **Hyvärinen Score** | L6 | Hyvärinen 2005; Ehm & Gneiting 2012 | Normalization-free proper scoring |
| **Model Diversity (DTVW)** | L4 | arXiv 2508.07136 (2025) | Redundancy penalty, effective source count |
| **Directed-evidence log-odds update** | L0/L4 | This framework | Evidence targets a specific outcome, avoiding probability flattening |

---

## 3. Quick Start

```python
from edp import EDP, GenericDomain, Outcome, Evidence

# 1. Define the problem domain (any "outcomes + signals" problem)
domain = GenericDomain([
    Outcome("rain", "Rain"),
    Outcome("no_rain", "No rain"),
])

# 2. Initialize EDP
edp = EDP(domain)

# 3. Pass in information sources — one-shot analysis
result = edp.analyze(
    evidence=[
        Evidence("weather_model", "model", {"probability": 0.72}, confidence=0.8),
        Evidence("satellite", "sensor", {"probability": 0.68}, confidence=0.9),
        Evidence("historical", "model", {"probability": 0.60}, confidence=0.5),
    ],
    budget=1000,
)

print(result["summary"])
# Most likely: rain (~68%) | Sources: 3 | Consensus: 0.91 | Allocation: ...
print(result["probabilities"])
# {"rain": 0.68, "no_rain": 0.32}
```

See `examples/python/basic_usage.py`.

---

## 4. Entry Points (MCP / Python API / Agent Skills / CLI)

EDP is designed to be **highly adaptive**: the same seven-layer engine can
be used through multiple entry points by different roles — AI assistants,
Python developers, Agent frameworks, command-line scripts. All entry
points share the same `EDP` core implementation and behave identically.

```
                 ┌─────────────────────────────────────┐
                 │   EDP Seven-Layer Core Engine        │
                 │  (src/python)                        │
                 │  L0 data → L1 extract → L2 infer     │
                 │  → L3 flow → L4 fuse → L5 allocate   │
                 │  → L6 calibrate → L7 conformal       │
                 └──────────────┬──────────────────────┘
                                │
   ┌────────────┬───────────────┼───────────────┬─────────────┐
   ▼            ▼               ▼               ▼             ▼
 MCP Server  Python API    Agent Skills       CLI        Notebook
 (AI helper) (developer)   (Agent framework)  (script)   (research)
```

### 4.1 MCP Server — Giving AI Assistants Forecasting Ability

[`mcp/server.py`](mcp/server.py) exposes EDP as a Model Context Protocol
server. Any MCP-compatible client (Claude Desktop, etc.) can call six
tools:

| Tool | Layer | Purpose |
|------|-------|---------|
| `analyze_situation` | L0–L7 | One-shot full-stack analysis (domain + evidence + conformal + allocation) |
| `calculate_true_probability` | L1 | Shin normalization: extract true probabilities from quotes |
| `assess_situation` | L4 | Multi-source intelligence fusion (linear / log-odds / Bayesian) |
| `conformal_predict` | L7 | Conformal prediction set (finite-sample coverage guarantee) |
| `online_aggregate` | L2 | Online expert aggregation (ML-Poly / EWA / Ridge / Bayesian Stacking) |
| `evaluate_prediction` | L6 | Calibration scoring (Brier / Log / Hyvärinen) |

```bash
python mcp/server.py
```

See [`mcp/README.md`](mcp/README.md).

### 4.2 Python API — Embed in Your Application

Import directly as a library, suitable for data pipelines, web backends,
research scripts:

```python
from edp import EDP, GenericDomain, Outcome, Evidence

domain = GenericDomain([Outcome("a", "Outcome A"), Outcome("b", "Outcome B")])
edp = EDP(domain)
result = edp.analyze(evidence=[...], budget=1000)
```

Install: `pip install edp-framework` (or dev mode `pip install -e ".[dev]"`).
All public symbols are listed in `__all__` of
[`src/python/__init__.py`](src/python/__init__.py).

### 4.3 Agent Skills — Wrapping as a Skill for Agent Frameworks

EDP's `DomainAdapter` + `GenericDomain` abstractions allow any
"outcomes + signals" problem to be modeled uniformly, so it can be wrapped
as a **reusable Skill** by any Agent framework:

- Input contract: `outcomes[]` + `evidence[]` (each evidence carries
  `source_type`, `probability`, optional `outcome_id`, `confidence`)
- Output contract: `probabilities` + `prediction_set` + `summary` + optional `allocation`
- Domain-agnostic: weather, funding rounds, match scores, fault diagnosis — same interface

Agent frameworks only need to wrap the MCP tools above or the Python API
with a Skill descriptor. The MCP entry point is recommended
(transport-agnostic, cross-framework).

### 4.4 CLI / Script — One-Shot Analysis

No long-running process needed — run a one-shot analysis directly:

```bash
python examples/python/basic_usage.py
```

Research scenarios in [`examples/notebooks/`](examples/notebooks/)
(including `startup_funding.ipynb`, `football_score.ipynb`).

---

## 5. Project Structure

```
edp/
├── src/python/
│   ├── __init__.py            # package exports
│   ├── core.py                # L0: Outcome/Quote/Evidence/Snapshot/EventGraph/DomainAdapter
│   ├── probability_engine.py  # L1-3: Shin/Bayesian/Flow/Glicko-2
│   ├── online_aggregator.py   # L2: ML-Poly/EWA/Ridge/Online Bayesian Stacking
│   ├── flow_amplification.py  # L3: Amplification/BFS/Cascade
│   ├── domain_awareness.py    # L4: Fusion/Consensus/Anomaly/Model diversity
│   ├── allocation_engine.py   # L5: Kelly/Markowitz/Three Principles
│   ├── calibration.py         # L6: Brier/Log/Hyvärinen/CRPS/Calibration curve
│   ├── conformal.py           # L7: Split Conformal/ACI/AgACI (2025 frontier)
│   └── edp.py                 # Top-level EDP interface
├── tests/python/
├── examples/python/           # basic_usage.py
├── examples/notebooks/        # startup_funding.ipynb / football_score.ipynb
├── mcp/server.py              # MCP Server (exposes EDP to AI assistants)
├── docs/theory/references.md
├── CHANGELOG.md               # Changelog
├── CONTRIBUTING.md            # Contributing guide
├── CODE_OF_CONDUCT.md         # Code of conduct
└── SECURITY.md                # Security policy
```

---

## 6. Upgrading from V1 to V2.0

Major changes from V1 (4.1) to V2.0:

| Change | V1 (4.1) | V2.0 |
|--------|----------|------|
| Architecture layers | 5 | 7 (added Calibration L6 + Conformal L7) |
| Top-level interface | None | `EDP` class one-shot analysis |
| Domain adaptation | Hard-coded | `DomainAdapter` + `GenericDomain` |
| Event relations | Fixed | `EventGraph` (chain / complete / custom) |
| Online aggregation | None | `OnlineAggregator` (ML-Poly/EWA/Ridge/Online Bayesian Stacking) |
| Calibration | None | `CalibrationEngine` (Brier/Log/Hyvärinen/calibration curve) |
| Conformal prediction | None | `ConformalEngine` (Split/ACI/AgACI, finite-sample coverage) |
| Directed evidence | None | `Evidence.outcome_id` (targets a specific outcome, avoiding flattening) |
| Risk warning | Brief | Strengthened at top of every module + detailed AllocationEngine warning |

V1's `flow_analyzer.py` and `scheme_designer.py` were removed; their
functionality was merged into `flow_amplification.py` and
`allocation_engine.py` respectively.

---

## 7. References & Related Work

EDP stands on the shoulders of giants. Each layer has a clear academic
provenance — see [`docs/theory/references.md`](docs/theory/references.md).

### 7.1 Theoretical Basis by Layer (Related Work)

| Layer | Method | Reference |
|-------|--------|-----------|
| L1 | Shin normalization | Shin (1992), *Economic Journal* 102(411) |
| L2 | Beta-Binomial conjugacy | Gelman et al. (2013), *BDA3* |
| L2 | Glicko-2 rating | Glickman (2001), *J. Appl. Stat.* 28(6) |
| L2 | Online Bayesian Stacking | Waxman et al. (2025), arXiv:2505.15638 |
| L3 | Time-series momentum | Moskowitz et al. (2012), *JFE* 104(2) |
| L3 | Information cascades | Banerjee (1992), *QJE* 107(3) |
| L4 | Linear / log-odds opinion pools | Cooke (1991); Genest & Zidek (1986) |
| L4 | Model diversity (DTVW) | Luo et al. (2025), arXiv:2508.07136 |
| L5 | Kelly criterion / Markowitz | Kelly (1956); Markowitz (1952) |
| L6 | Proper scoring (Hyvärinen) | Hyvärinen (2005); Ehm & Gneiting (2012) |
| L7 | Conformal / ACI / AgACI | Gibbs & Candès (2021); Zaffran et al. (2022) |

> Academic-accuracy note: EDP's code implements **Glicko-2** (with volatility σ),
> hence cites Glickman (2001), *Dynamic Paired Comparison Models with Stochastic
> Variances*. Glickman (1999) describes Glicko-1 (no volatility) and does not apply.

### 7.2 Citing This Project

If you use EDP in academic work, please cite it as described in
[`CITATION.cff`](CITATION.cff) (GitHub renders an APA/BibTeX export button).

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

## Community Files

| File | Description |
|------|-------------|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Contributing guide (workflow, conventions, commit style) |
| [`CHANGELOG.md`](CHANGELOG.md) | Changelog (Keep a Changelog format) |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Code of conduct (Contributor Covenant 2.1) |
| [`SECURITY.md`](SECURITY.md) | Security policy & vulnerability reporting |
| [`CITATION.cff`](CITATION.cff) | Academic citation metadata |
| [`.github/`](.github/) | Issue/PR templates, CODEOWNERS, CI/Release/Stale workflows |

Join us in [Discussions](https://github.com/ai-nurmamat/EDP/discussions);
file bugs as [Issues](https://github.com/ai-nurmamat/EDP/issues);
report security vulnerabilities privately per [`SECURITY.md`](SECURITY.md).

---

*EDP V2.0 — A Universal Domain-Aware Probabilistic Situation Awareness Framework*
*Any problem decomposable into "outcomes + signals" can be handled by it.*
*For academic research and educational purposes only.*

---

## Appendix A. Mathematical Foundations (legacy)

> The detailed V1-era derivations below are kept for in-depth reference.
> For daily use, refer to the V2.0 seven-layer architecture above.

---

### A.1 Shin Normalization — Extraction of True Probabilities

Market quotes embed a profit margin ("overround") and therefore cannot be
directly interpreted as probabilities. Shin (1992) proposed a model
assuming the margin is proportional to the presence of "insider traders,"
allowing one to invert the relationship and recover "true probabilities."

**Formal problem**: Given quotes *q₁, q₂, …, qN* for *N* outcomes, where
*qᵢ > 1* in decimal odds.

**Implied probabilities**: πᵢ = 1/qᵢ. The market overround is:

> Σᵢ₌₁ᴺ πᵢ − 1 > 0

**Shin iterative scheme** for true probabilities *p*:

> pᵢᵏ⁺¹ = (πᵢ − zᵏ √pᵢᵏ) / (1 − zᵏ Σⱼ √pⱼᵏ)

where *z* is the estimated insider-trade proportion; iterate until
|pᵢᵏ⁺¹ − pᵢᵏ| < ε.

**Reference**: Shin, H.S. (1992). *Prices of State-Contingent Claims with
Insider Traders*. Economic Journal, 102(411), 426–435.

### A.2 Beta-Binomial Conjugate Bayesian Inference

For Bernoulli trials, the Beta distribution provides a conjugate prior:

- **Prior**: Beta(α₀, β₀)
- **Observation**: *k* successes in *n* trials
- **Posterior**: Beta(α₀ + k, β₀ + n − k)

**Posterior mean**:

> E[p | evidence] = (α₀ + k) / (α₀ + β₀ + n)

**95% Credible interval** via the normal approximation:

> CI₉₅ = p̂ ± 1.96 × √(p̂(1 − p̂)/(n_eff + 1))

**Reference**: Gelman, A., Carlin, J.B., Stern, H.S., & Rubin, D.B. (2013).
*Bayesian Data Analysis*, 3rd ed. Chapman & Hall/CRC.

### A.3 Glicko-2 Rating System

An advancement over Elo, introducing rating deviation (RD) and volatility
(σ) for more robust dynamic strength modeling.

**Core update equations** (in Glicko-2 scale: μ, φ, σ):

> E(μ, μⱼ, φⱼ) = 1 / (1 + exp(−g(φⱼ)(μ − μⱼ)))

> g(φ) = 1 / √(1 + 3φ²/π²)

> ν = [ Σⱼ g(φⱼ)² E(1 − E) ]⁻¹

> Δ = ν · Σⱼ g(φⱼ) (sⱼ − E)

where ν is the estimated variance and Δ the improvement deviation.

**Reference**: Glickman, M.E. (2001). *Dynamic Paired Comparison Models
with Stochastic Variances*. Journal of Applied Statistics, 28(6), 673–689.
(See §7.1 note on Glickman 1999 vs 2001.)

### A.4 Probability Flow Analysis

**Definition** (within a time interval Δt):

> Flowᵢ = pᵢ(t + Δt) − pᵢ(t)

**Time-series momentum score** (Moskowitz et al., 2012):

> momentum_score = Σ_t w_t · flow_t,  where Σ_t w_t = 1

**Velocity and acceleration**:

> vᵢ = d(Flowᵢ) / dt,   aᵢ = d²(Flowᵢ) / dt²

**Significance thresholds**: |flow| < 0.5% stable; 0.5%–2% low; 2%–5%
medium; ≥5% high.

### A.5 Flow Amplification Score

The amplification score for outcome *i* combines four factors:

> AmpScoreᵢ = BaseFlowᵢ × DirConsistᵢ × (1 + GradientPosᵢ) × MarketMomentum

- **Directional consistency** *DirConsistᵢ*: fraction of adjacent outcomes whose flow is aligned with the target outcome
- **Gradient position** *GradientPosᵢ*: normalized probability level — lower-probability outcomes carry higher amplification potential
- **Market momentum** *MarketMomentum*: mean momentum across all outcomes

### A.6 Multi-Source Intelligence Fusion

A **hybrid fusion strategy** is adopted — a weighted combination of linear
and log-odds opinion pools:

**Linear opinion pool** (Cooke, 1991):

> p_linear = Σᵢ wᵢ · pᵢ,  where Σᵢ wᵢ = 1

**Log-odds opinion pool** (Genest & Zidek, 1986):

> logit(p_logodds) = Σᵢ wᵢ · logit(pᵢ)

**Hybrid estimate**:

> p_fused = α · p_linear + (1 − α) · p_logodds,  α ∈ [0, 1]

**Source weights** are three-dimensional:

> wᵢ = reliabilityᵢ × confidenceᵢ × temporal_decayᵢ

> temporal_decayᵢ = 2^(−Δtᵢ / t½)

**Consensus score** (based on dispersion of source estimates):

> Consensus = 1 − min(σ_observed / σ_max, 1.0)

where σ_max = 0.5 is the theoretical maximum standard deviation for a
Bernoulli(p=0.5) distribution.

### A.7 Kelly-Optimal Capital Allocation

The Kelly Criterion maximizes the expected log-wealth growth rate:

> f* = (p · b − q) / b = (p(b + 1) − 1) / b

where *p* is the win probability, *b* the net decimal odds (quote − 1),
and *q = 1 − p*.

**Fractional Kelly** (framework default: quarter-Kelly, 1/4):

> f = κ · f*,  κ ∈ (0, 1]

This controls volatility at the expense of a reduced expected growth rate.

**Three Principles of Allocation**:
1. **Signal Alignment** — Only allocate to outcomes with positive probability-flow signals
2. **Asymmetric Potential** — Require positive expectation (odds × probability > 1)
3. **Risk Diversification** — Cap concentration ≤ 20% and maintain diversification ratio

---

## Appendix B. Core Engines (legacy)

### B.1 ProbabilityEngine

| Module | Theoretical Basis | Output |
|--------|-------------------|--------|
| True probability calculation | Shin normalization / iterative method | p_true, margin, CI |
| Conditional probability | Bayesian conditional definition | p(A \| B) |
| Bayesian update | Beta-Binomial conjugate model | posterior α, β, CI |
| Prior fusion | Log-odds / linear pool | combined posterior |
| Glicko-2 ratings | Glickman (2001) | μ, RD, σ |
| Flow analysis | Time-series momentum | flow_velocity, acceleration |

### B.2 FlowAnalyzer

| Module | Theoretical Basis | Output |
|--------|-------------------|--------|
| Base flow | Differenced time series | Δp, v, a |
| Directional consistency | Adjacency-structure scoring | 0–1 consistency coefficient |
| Gradient position | Inverse mapping on probability simplex | 0–1 amplification potential |
| Market momentum | Weighted aggregate momentum | aggregate_momentum |
| Cascade risk | Information cascade theory | Risk level tagging |

### B.3 DomainAwarenessEngine

| Module | Theoretical Basis | Output |
|--------|-------------------|--------|
| Evidence preprocessing | Source reliability rating (STANAG 2511 adaptation) | w_i, normalized weights |
| Linear pool fusion | Cooke (1991) opinion pool | p_linear |
| Log-odds pool fusion | Genest & Zidek (1986) | p_logodds |
| Bayesian accumulation | Pearl (1988) sequential updating | posterior log-odds |
| Consensus analysis | Variance-dispersion transform | consensus_score |
| Anomaly detection | Z-score thresholding | anomaly list |
| Cascade detection | Information cascade theory (Bikhchandani 1992) | potential_cascade flag |
| Situation assessment | Stability classifier | aggregate_probability, confidence, status |

### B.4 AllocationEngine

| Module | Theoretical Basis | Output |
|--------|-------------------|--------|
| Validity check | Three allocation principles | valid / warning / invalid |
| Kelly allocation | Kelly (1956) information-rate criterion | fraction, amount |
| Risk stratification | Probability-odds mapping | conservative / balanced / aggressive / extreme |
| Markowitz rebalancing | Concentration cap + diversification ratio | optimized allocation |
| Portfolio statistics | Expected value / risk contribution | portfolio_EV, diversification_ratio |

---

## Appendix C. Implementation Specifications (legacy)

### C.1 Technical Stack

| Aspect | Technology |
|--------|------------|
| Programming Languages | Python 3.10+, TypeScript 5.0+ |
| Type Safety | Full type annotations (dataclass, Enum) |
| Numerical Precision | IEEE 754 double-precision |
| Convergence Criterion | ε = 1e-10 (Shin iterations) |
| Iteration Cap | 100 iterations |

### C.2 Code Quality and Validation

- **Linting**: ruff — static syntax and style verification
- **Formatting**: black — standard style unification
- **Type checking**: mypy strict — static type verification
- **Test framework**: pytest (Python) / Jest (TypeScript, legacy)

---

## Appendix D. Key References (legacy)

| Theory / Method | Citation |
|-----------------|----------|
| Shin Normalization | Shin, H.S. (1992). *Prices of State-Contingent Claims with Insider Traders*. Economic Journal, 102(411), 426–435. |
| Bayesian Inference | Gelman, A., Carlin, J.B., Stern, H.S., & Rubin, D.B. (2013). *Bayesian Data Analysis*, 3rd ed. Chapman & Hall/CRC. |
| Time-Series Momentum | Moskowitz, T.J., Ooi, Y.H., & Pedersen, L.H. (2012). *Time Series Momentum*. Journal of Financial Economics, 104(2), 228–250. |
| Glicko-2 Rating | Glickman, M.E. (2001). *Dynamic Paired Comparison Models with Stochastic Variances*. Journal of Applied Statistics, 28(6), 673–689. |
| Elo Rating System | Elo, A.E. (1978). *The Rating of Chessplayers, Past and Present*. Arco. |
| Information Cascades | Banerjee, A.V. (1992). *A Simple Model of Herd Behavior*. Quarterly Journal of Economics, 107(3), 797–817. |
| | Bikhchandani, S., Hirshleifer, D., & Welch, I. (1992). *A Theory of Fads, Fashion, Custom, and Cultural Change as Information Cascades*. JPE, 100(5), 992–1026. |
| Probability Distribution Fusion | Genest, C., & Zidek, J.V. (1986). *Combining Probability Distributions: A Critique and an Annotated Bibliography*. Statistical Science, 1(1), 114–135. |
| Consensus Dynamics | DeGroot, M.H. (1974). *Reaching a Consensus*. JASA, 69(345), 118–121. |
| Expert Uncertainty | Cooke, R.M. (1991). *Experts in Uncertainty*. Oxford University Press. |
| Kelly Criterion | Kelly, J.L. (1956). *A New Interpretation of Information Rate*. Bell System Technical Journal, 35(4), 917–926. |
| Portfolio Theory | Markowitz, H.M. (1952). *Portfolio Selection*. Journal of Finance, 7(1), 77–91. |
| Prospect Theory | Kahneman, D., & Tversky, A. (1979). *Prospect Theory: An Analysis of Decision Under Risk*. Econometrica, 47(2), 263–291. |
| Bayesian Networks | Pearl, J. (1988). *Probabilistic Reasoning in Intelligent Systems*. Morgan Kaufmann. |
| Information Theory | Cover, T.M., & Thomas, J.A. (2006). *Elements of Information Theory*, 2nd ed. Wiley. |

---

## Appendix E. Usage Examples (legacy)

### E.1 Python Interface

```python
from edp import (
    ProbabilityEngine,
    FlowAmplificationEngine,
    DomainAwarenessEngine,
    AllocationEngine,
    AllocationLeg,
)

# ── Initialize engines ─────────────────────────────────
prob_engine = ProbabilityEngine()
flow_engine = FlowAmplificationEngine()
domain_engine = DomainAwarenessEngine()
alloc_engine = AllocationEngine()

# ── 1. Compute true probabilities from market quotes ──
result = prob_engine.calculate_true_probability({
    "home": 1.50, "draw": 4.20, "away": 6.00
})
# Fields: true_probabilities, margin, confidence_interval, method

# ── 2. Probability flow analysis (time series) ─────────
flow_report = prob_engine.analyze_flow(
    initial_snapshot=snapshot_t0,
    latest_snapshot=snapshot_t1,
    historical_snapshots=history,
)
# Fields: flows (per-outcome flow / velocity / acceleration / significance),
#         aggregate_momentum, time_delta

# ── 3. Flow amplification scoring ─────────────────────
amp_report = flow_engine.calculate_amplification(
    flow_report,
    gradient_map={"home": ["draw"], "away": ["draw"]},
    outcome_probs=result.true_probabilities,
)

# ── 4. Domain awareness · multi-source fusion ──────────
from edp import EvidenceSource, SourceReliability, EvidenceType

sources = [
    EvidenceSource(
        source_id="model_01",
        source_type=EvidenceType.ANALYTICAL,
        reliability=SourceReliability.B,   # usually reliable
        timestamp=datetime.now(),
        content={"probability": 0.62},
        confidence=0.80,
    ),
    # ... additional intelligence sources
]

assessment = domain_engine.assess_situation(
    sources,
    prior_probability=0.5,
    fusion_method="hybrid",
)
# Fields: aggregate_probability, confidence, consensus_score,
#         stability_status, anomalies, variance

# ── 5. Capital allocation (Kelly + Markowitz) ─────────
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

### E.2 TypeScript Interface (LEGACY)

> Note: `src/js/` is a V1 legacy implementation kept for reference only.
> The V2.0 authoritative implementation is Python, exposed to all
> languages via MCP.

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

## Appendix F. Disclaimer (legacy)

**This framework is for academic research and educational purposes only.**

- This framework does not constitute any investment advice or decision-making recommendation;
- Any decisions made using this framework are the sole responsibility of the user;
- The authors are not responsible for any losses incurred through the use of this framework;
- Please comply with laws and regulations in your jurisdiction.

---

## Appendix G. License

MIT License — see the *LICENSE* file in the repository root.

---

*Providing academic research support through structured analysis, rigorous
probability theory, and domain-wide cognition — for academic research
purposes only.*

*© 2026 — For Academic Research and Educational Purposes Only.*
