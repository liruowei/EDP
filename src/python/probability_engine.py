"""
EDP - 期望域感知方法 (Expectation Domain Perception Method) V2.0
概率提取 + 贝叶斯推断 + 流向分析引擎 (Layer 1 + 2 + 3)

本模块实现：
    - Shin 归一化：从市场报价提取真实概率（Shin, 1992）
    - Beta-Binomial 共轭贝叶斯推断
    - 多源先验融合（对数池/线性池）
    - Glicko-2 评级系统（Glickman, 1999）
    - 概率流向分析（Moskowitz et al., 2012）

数学基础：
    Shin 归一化:     H. S. Shin (1992) - "Prices of State-Contingent Claims
                     with Insider Traders", Economic Journal, 102(411), 426-435.
    贝叶斯推断:      Gelman et al. (2013) - "Bayesian Data Analysis" (3rd ed.)
    时间序列动量:    Moskowitz, Ooi & Pedersen (2012)
    Glicko-2 评级:   Mark Glickman (1999) - "Parameter Estimation in Large
                     Dynamic Paired Comparison Systems"

⚠️ 风险警示 ⚠️
    本模块仅供学术研究与教育用途。计算结果为统计推断产物，
    不构成任何投资建议、决策建议或交易指导。历史概率模式不保证
    未来结果。使用者须自行承担一切决策风险。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from .core import Snapshot

# ======================================================================
# Enums and Constants
# ======================================================================


class FlowDirection(Enum):
    """概率流向分类。"""

    UPWARD = "upward"  # 概率上升
    DOWNWARD = "downward"  # 概率下降
    STABLE = "stable"  # 无显著变化


# 统计常数
SHIN_ITERATIONS = 100  # Shin 迭代收敛上限
SHIN_TOLERANCE = 1e-10  # 收敛阈值
BETA_PRIOR_STRENGTH = 2.0  # Beta 先验默认样本量


# ======================================================================
# Data Classes
# ======================================================================


@dataclass
class TrueProbabilityResult:
    """真实概率计算结果（Shin 归一化后）。"""

    true_probabilities: dict[str, float]
    implied_probabilities: dict[str, float]
    market_margin: float
    margin_per_outcome: dict[str, float]
    method: str = "shin_normalized"
    confidence_interval: dict[str, tuple[float, float]] | None = None

    @property
    def overround(self) -> float:
        """市场边际（别名）。"""
        return self.market_margin

    def get_most_likely_outcome(self) -> tuple[str, float]:
        """返回概率最高的结果。"""
        return max(self.true_probabilities.items(), key=lambda x: x[1])

    def get_probability_ranking(self) -> list[tuple[str, float]]:
        """按概率降序排列。"""
        return sorted(self.true_probabilities.items(), key=lambda x: x[1], reverse=True)


@dataclass
class BayesianPrior:
    """
    Beta 分布先验 Beta(alpha, beta)。

    Attributes:
        alpha: 形状参数（成功数+1）
        beta: 形状参数（失败数+1）
        source: 先验来源标识
        weight: 融合时的权重
    """

    alpha: float
    beta: float
    source: str = "default"
    weight: float = 1.0

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        a, b = self.alpha, self.beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1))

    @property
    def effective_sample_size(self) -> float:
        return self.alpha + self.beta


@dataclass
class BayesianPosterior:
    """Beta-Binomial 共轭后验分布。"""

    posterior_alpha: float
    posterior_beta: float
    expected_probability: float
    std_deviation: float
    credible_interval: tuple[float, float]
    update_evidence: dict[str, Any]

    @property
    def variance(self) -> float:
        a, b = self.posterior_alpha, self.posterior_beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1))

    @property
    def effective_sample_size(self) -> float:
        return self.posterior_alpha + self.posterior_beta


@dataclass
class FlowResult:
    """单个结果的概率流向分析结果。"""

    outcome: str
    flow_pp: float  # 流向（百分点）
    direction: FlowDirection
    initial_prob: float
    latest_prob: float
    momentum_score: float
    significance: str = "low"  # low / medium / high
    velocity: float = 0.0
    acceleration: float = 0.0

    def is_significant(self, threshold: float = 2.0) -> bool:
        return abs(self.flow_pp) >= threshold

    def get_confidence_level(self) -> float:
        base = min(abs(self.flow_pp) / 10.0, 1.0)
        bonus = min(self.momentum_score / 5.0, 0.2)
        return min(base + bonus, 1.0)


@dataclass
class FlowReport:
    """完整流向分析报告。"""

    initial_snapshot: Snapshot
    latest_snapshot: Snapshot
    flows: list[FlowResult] = field(default_factory=list)
    time_delta: timedelta = field(default_factory=timedelta)
    generated_at: datetime = field(default_factory=datetime.now)
    aggregate_momentum: float = 0.0

    @property
    def match_id(self) -> str:
        return f"flow_{self.initial_snapshot.timestamp.timestamp():.0f}"

    def get_upward_flows(self) -> list[FlowResult]:
        return [f for f in self.flows if f.direction == FlowDirection.UPWARD]

    def get_downward_flows(self) -> list[FlowResult]:
        return [f for f in self.flows if f.direction == FlowDirection.DOWNWARD]

    def get_significant_flows(self, threshold: float = 2.0) -> list[FlowResult]:
        return [f for f in self.flows if f.is_significant(threshold)]

    def get_flow_summary(self) -> dict[str, Any]:
        upward = self.get_upward_flows()
        downward = self.get_downward_flows()
        stable = [f for f in self.flows if f.direction == FlowDirection.STABLE]
        return {
            "total_outcomes": len(self.flows),
            "upward_count": len(upward),
            "downward_count": len(downward),
            "stable_count": len(stable),
            "aggregate_momentum": self.aggregate_momentum,
            "time_delta_hours": self.time_delta.total_seconds() / 3600,
            "significant_flows": [
                {"outcome": f.outcome, "flow_pp": f.flow_pp, "significance": f.significance}
                for f in self.get_significant_flows()
            ],
        }


@dataclass
class Glicko2Rating:
    """
    Glicko-2 评级系统（动态实力建模）。

    参考: Mark Glickman (1999)
    """

    team_id: str
    rating: float = 1500.0
    rd: float = 350.0  # Rating deviation
    volatility: float = 0.06
    games_played: int = 0
    last_game_date: datetime | None = None
    rating_history: list[tuple[datetime, float]] = field(default_factory=list)

    TAU = 1.0
    CONVERGENCE_TOLERANCE = 1e-8
    SCALE_FACTOR = 173.7178

    def expected_score(self, opponent_rating: float, opponent_rd: float) -> float:
        """计算对对手的期望得分。"""
        mu = (self.rating - 1500.0) / self.SCALE_FACTOR
        mu_opp = (opponent_rating - 1500.0) / self.SCALE_FACTOR
        rd_opp = opponent_rd / self.SCALE_FACTOR
        g_rd = 1.0 / math.sqrt(1.0 + 3.0 * rd_opp**2 / math.pi**2)
        return 1.0 / (1.0 + math.exp(-g_rd * (mu - mu_opp)))

    def update_rating(self, results: list[tuple[float, float, float]]) -> None:
        """
        根据比赛结果更新评级。

        Args:
            results: [(actual_score, opponent_rating, opponent_rd), ...]
                     actual_score: 1.0 胜, 0.5 平, 0.0 负
        """
        if not results:
            return

        mu = (self.rating - 1500.0) / self.SCALE_FACTOR
        phi = self.rd / self.SCALE_FACTOR
        sigma = self.volatility

        v_sum = 0.0
        delta_sum = 0.0

        for actual_score, opp_rating, opp_rd in results:
            mu_opp = (opp_rating - 1500.0) / self.SCALE_FACTOR
            phi_opp = opp_rd / self.SCALE_FACTOR
            g_opp = 1.0 / math.sqrt(1.0 + 3.0 * phi_opp**2 / math.pi**2)
            expected = 1.0 / (1.0 + math.exp(-g_opp * (mu - mu_opp)))
            v_sum += g_opp**2 * expected * (1.0 - expected)
            delta_sum += g_opp * (actual_score - expected)

        v = 1.0 / v_sum if v_sum > 0 else 1.0
        delta = v * delta_sum

        # 简化的波动率更新
        new_sigma = self.TAU if abs(delta) > self.TAU else sigma

        phi_star = math.sqrt(phi**2 + new_sigma**2)
        new_phi = 1.0 / math.sqrt(1.0 / phi_star**2 + 1.0 / v)
        new_mu = mu + new_phi**2 * delta_sum

        self.rating = 1500.0 + self.SCALE_FACTOR * new_mu
        self.rd = self.SCALE_FACTOR * new_phi
        self.volatility = new_sigma
        self.games_played += len(results)
        self.rating_history.append((datetime.now(), self.rating))


# ======================================================================
# ProbabilityEngine
# ======================================================================


class ProbabilityEngine:
    """
    概率提取 + 贝叶斯 + 流向分析引擎 (L1 + L2 + L3)。

    功能：
        - calculate_true_probability(quotes) → 真实概率（Shin 归一化）
        - bayesian_update(prior, successes, trials) → 后验
        - combine_priors(priors, evidence) → 多源先验融合
        - analyze_flow(initial, latest, history?) → 流向分析报告
        - update_glicko_rating(team, results) → Glicko-2 评级
        - calculate_conditional_probability(probs, condition) → 条件概率

    ⚠️ 本引擎仅供学术研究，输出不构成任何决策建议。
    """

    FLOW_THRESHOLD_LOW = 0.5
    FLOW_THRESHOLD_MEDIUM = 2.0
    FLOW_THRESHOLD_HIGH = 5.0

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.flow_threshold_low = self.config.get("flow_threshold_low", self.FLOW_THRESHOLD_LOW)
        self.flow_threshold_medium = self.config.get(
            "flow_threshold_medium", self.FLOW_THRESHOLD_MEDIUM
        )
        self.flow_threshold_high = self.config.get("flow_threshold_high", self.FLOW_THRESHOLD_HIGH)
        self.prior_strength = self.config.get("prior_strength", BETA_PRIOR_STRENGTH)
        self.evidence_weight = self.config.get("evidence_weight", 1.0)
        self.use_iterative_shin = self.config.get("use_iterative_shin", True)
        self.glicko_ratings: dict[str, Glicko2Rating] = {}

    # ------------------------------------------------------------------
    # 真实概率计算 (Shin 归一化)
    # ------------------------------------------------------------------

    def calculate_true_probability(
        self,
        implied_quotes: dict[str, float],
        method: str = "shin_normalized",
    ) -> TrueProbabilityResult:
        """
        从市场报价提取真实概率（Shin 方法去边际）。

        Args:
            implied_quotes: {outcome: decimal_quote}，decimal_quote > 1.0
            method: 'shin_normalized' (默认) 或 'iterative_shin'

        Returns:
            TrueProbabilityResult

        Raises:
            ValueError: 报价为空或无效
        """
        if not implied_quotes:
            raise ValueError("Quotes dictionary cannot be empty")

        for outcome, quote in implied_quotes.items():
            if quote <= 1.0:
                raise ValueError(f"Invalid quote value for {outcome}: {quote}")

        implied_probs = {o: 1.0 / q for o, q in implied_quotes.items()}
        market_margin = sum(implied_probs.values()) - 1.0
        total_implied = sum(implied_probs.values())
        margin_per_outcome = {
            o: (p / total_implied) * market_margin for o, p in implied_probs.items()
        }

        if method == "iterative_shin" and self.use_iterative_shin:
            true_probs = self._iterative_shin_method(implied_probs)
        else:
            true_probs = {o: p / total_implied for o, p in implied_probs.items()}

        # Wilson 置信区间
        n = len(true_probs)
        conf_intervals: dict[str, tuple[float, float]] = {}
        z = 1.96
        for outcome, prob in true_probs.items():
            denom = 1 + z**2 / n
            center = (prob + z**2 / (2 * n)) / denom
            width = z * math.sqrt(prob * (1 - prob) / n + z**2 / (4 * n**2)) / denom
            conf_intervals[outcome] = (max(0.0, center - width), min(1.0, center + width))

        return TrueProbabilityResult(
            true_probabilities=true_probs,
            implied_probabilities=implied_probs,
            market_margin=market_margin,
            margin_per_outcome=margin_per_outcome,
            method=method,
            confidence_interval=conf_intervals,
        )

    def _iterative_shin_method(self, implied_probs: dict[str, float]) -> dict[str, float]:
        """Shin 迭代法求解真实概率。"""
        n = len(implied_probs)
        if n == 0:
            return {}

        total = sum(implied_probs.values())
        true_probs = {k: v / total for k, v in implied_probs.items()}

        for _ in range(SHIN_ITERATIONS):
            sqrt_sum = sum(math.sqrt(p) for p in true_probs.values())
            if sqrt_sum == 0:
                break

            market_margin = sum(implied_probs.values()) - 1.0

            if sqrt_sum <= 1.0:
                total_p = sum(true_probs.values())
                true_probs = {k: v / total_p for k, v in true_probs.items()}
                break

            z = min(market_margin / max(sqrt_sum - 1.0, 0.001), 0.999)

            new_probs = {}
            for key, impl_prob in implied_probs.items():
                sqrt_p = math.sqrt(true_probs[key])
                new_prob = (impl_prob - z * sqrt_p) / (1.0 - z * sqrt_sum)
                new_probs[key] = max(new_prob, 1e-10)

            max_change = max(abs(new_probs[k] - true_probs[k]) for k in true_probs)
            true_probs = new_probs

            if max_change < SHIN_TOLERANCE:
                break

        total_final = sum(true_probs.values())
        return {k: v / total_final for k, v in true_probs.items()}

    # ------------------------------------------------------------------
    # 条件概率
    # ------------------------------------------------------------------

    def calculate_conditional_probability(
        self,
        outcome_probabilities: dict[str, float],
        condition_outcomes: list[str],
    ) -> dict[str, float]:
        """计算条件概率 P(A|B) = P(A∩B)/P(B)。"""
        condition_total = sum(outcome_probabilities.get(o, 0.0) for o in condition_outcomes)
        if condition_total == 0:
            return dict.fromkeys(condition_outcomes, 0.0)
        return {o: outcome_probabilities.get(o, 0.0) / condition_total for o in condition_outcomes}

    # ------------------------------------------------------------------
    # 贝叶斯推断
    # ------------------------------------------------------------------

    def bayesian_update(
        self,
        prior: BayesianPrior,
        evidence_successes: int,
        evidence_trials: int,
    ) -> BayesianPosterior:
        """
        Beta-Binomial 共轭贝叶斯更新。

        先验 Beta(α, β) + 观测 (k 成功, n 试验) → 后验 Beta(α+k, β+n-k)
        """
        if evidence_trials < 0:
            raise ValueError("Evidence trials must be non-negative")
        if evidence_successes < 0 or evidence_successes > evidence_trials:
            raise ValueError("Successes must be between 0 and trials")

        posterior_alpha = prior.alpha + evidence_successes
        posterior_beta = prior.beta + (evidence_trials - evidence_successes)
        expected_prob = posterior_alpha / (posterior_alpha + posterior_beta)
        variance = (posterior_alpha * posterior_beta) / (
            (posterior_alpha + posterior_beta) ** 2 * (posterior_alpha + posterior_beta + 1.0)
        )
        std_dev = math.sqrt(variance)

        z = 1.96
        lower = max(0.0, expected_prob - z * std_dev)
        upper = min(1.0, expected_prob + z * std_dev)

        return BayesianPosterior(
            posterior_alpha=posterior_alpha,
            posterior_beta=posterior_beta,
            expected_probability=expected_prob,
            std_deviation=std_dev,
            credible_interval=(lower, upper),
            update_evidence={
                "successes": evidence_successes,
                "trials": evidence_trials,
                "prior_source": prior.source,
                "prior_effective_sample_size": prior.effective_sample_size,
                "posterior_effective_sample_size": posterior_alpha + posterior_beta,
            },
        )

    def combine_priors(
        self,
        priors: list[BayesianPrior],
        new_evidence: dict[str, int] | None = None,
    ) -> BayesianPosterior:
        """
        加权融合多个先验（对数池化）。

            combined_alpha = Σ(w_i × α_i) / Σw_i
            combined_beta  = Σ(w_i × β_i) / Σw_i
        """
        if not priors:
            combined_alpha = 1.0
            combined_beta = 1.0
        else:
            total_weight = sum(p.weight for p in priors)
            combined_alpha = sum(p.alpha * p.weight for p in priors) / total_weight
            combined_beta = sum(p.beta * p.weight for p in priors) / total_weight

        if new_evidence:
            successes = new_evidence.get("successes", 0)
            trials = new_evidence.get("trials", 0)
            combined_alpha += successes
            combined_beta += max(trials - successes, 0)

        expected_prob = combined_alpha / (combined_alpha + combined_beta)
        variance = (combined_alpha * combined_beta) / (
            (combined_alpha + combined_beta) ** 2 * (combined_alpha + combined_beta + 1.0)
        )
        std_dev = math.sqrt(variance)

        z = 1.96
        lower = max(0.0, expected_prob - z * std_dev)
        upper = min(1.0, expected_prob + z * std_dev)

        return BayesianPosterior(
            posterior_alpha=combined_alpha,
            posterior_beta=combined_beta,
            expected_probability=expected_prob,
            std_deviation=std_dev,
            credible_interval=(lower, upper),
            update_evidence={
                "combined_priors": len(priors),
                "combined_method": "logarithmic_pooling",
                "additional_evidence": new_evidence is not None,
            },
        )

    # ------------------------------------------------------------------
    # Glicko-2 评级
    # ------------------------------------------------------------------

    def get_or_create_rating(self, team_id: str) -> Glicko2Rating:
        if team_id not in self.glicko_ratings:
            self.glicko_ratings[team_id] = Glicko2Rating(team_id=team_id)
        return self.glicko_ratings[team_id]

    def update_glicko_rating(
        self,
        team_id: str,
        results: list[tuple[float, float, float]],
    ) -> Glicko2Rating:
        """
        更新 Glicko-2 评级。

        Args:
            team_id: 队伍 ID
            results: [(actual_score, opponent_rating, opponent_rd), ...]
        """
        rating = self.get_or_create_rating(team_id)
        rating.update_rating(results)
        return rating

    def predict_with_rating(
        self,
        home_team: str,
        away_team: str,
        home_advantage: float = 100.0,
    ) -> dict[str, float]:
        """用 Glicko-2 评级预测比赛结果概率。"""
        home_rating = self.get_or_create_rating(home_team)
        away_rating = self.get_or_create_rating(away_team)

        effective_home_rating = home_rating.rating + home_advantage
        expected_home = home_rating.expected_score(away_rating.rating, away_rating.rd)
        expected_away = 1.0 - expected_home

        rating_diff = abs(effective_home_rating - away_rating.rating)
        draw_prob = max(0.15, 0.30 * math.exp(-rating_diff / 500.0))

        remaining = 1.0 - draw_prob
        home_win_prob = expected_home * remaining
        away_win_prob = expected_away * remaining

        total = home_win_prob + draw_prob + away_win_prob
        return {
            "home_win": home_win_prob / total,
            "draw": draw_prob / total,
            "away_win": away_win_prob / total,
        }

    # ------------------------------------------------------------------
    # 概率流向分析
    # ------------------------------------------------------------------

    def analyze_flow(
        self,
        initial_snapshot: Snapshot,
        latest_snapshot: Snapshot,
        historical_snapshots: list[Snapshot] | None = None,
    ) -> FlowReport:
        """
        分析两个时间点之间的概率流向。

            Flow(outcome) = P_latest(outcome) - P_initial(outcome)

        显著性分类：
            |Flow| < 0.5%:  stable
            0.5% ≤ |Flow| < 2%: low
            2% ≤ |Flow| < 5%:   medium
            |Flow| ≥ 5%:        high
        """
        flows: list[FlowResult] = []

        time_delta = latest_snapshot.timestamp - initial_snapshot.timestamp
        time_hours = max(time_delta.total_seconds() / 3600.0, 0.001)

        # 取所有结果 ID 的并集
        all_outcomes = set(initial_snapshot.probabilities) | set(latest_snapshot.probabilities)

        for outcome in all_outcomes:
            initial_prob = initial_snapshot.probabilities.get(outcome, 0.0)
            latest_prob = latest_snapshot.probabilities.get(outcome, initial_prob)
            flow_pp = (latest_prob - initial_prob) * 100.0

            if flow_pp > self.flow_threshold_low:
                direction = FlowDirection.UPWARD
            elif flow_pp < -self.flow_threshold_low:
                direction = FlowDirection.DOWNWARD
            else:
                direction = FlowDirection.STABLE

            abs_flow = abs(flow_pp)
            if abs_flow >= self.flow_threshold_high:
                significance = "high"
            elif abs_flow >= self.flow_threshold_medium:
                significance = "medium"
            else:
                significance = "low"

            momentum_score = flow_pp
            velocity = flow_pp / time_hours
            acceleration = 0.0

            if historical_snapshots and len(historical_snapshots) >= 2:
                historical_flows: list[float] = []
                sorted_snaps = sorted(
                    historical_snapshots + [initial_snapshot], key=lambda s: s.timestamp
                )
                for i in range(1, len(sorted_snaps)):
                    prev_prob = sorted_snaps[i - 1].probabilities.get(outcome, initial_prob)
                    curr_prob = sorted_snaps[i].probabilities.get(outcome, prev_prob)
                    delta_t = (
                        sorted_snaps[i].timestamp - sorted_snaps[i - 1].timestamp
                    ).total_seconds() / 3600.0
                    if delta_t > 0:
                        historical_flows.append((curr_prob - prev_prob) * 100.0 / delta_t)

                if len(historical_flows) >= 2:
                    weights = [1.0 / (i + 1) for i in range(len(historical_flows))]
                    total_w = sum(weights)
                    momentum_score = (
                        sum(w * f for w, f in zip(weights, historical_flows, strict=True)) / total_w
                    )
                    acceleration = velocity - historical_flows[-1] if historical_flows else 0.0

            flows.append(
                FlowResult(
                    outcome=outcome,
                    flow_pp=flow_pp,
                    direction=direction,
                    initial_prob=initial_prob,
                    latest_prob=latest_prob,
                    momentum_score=momentum_score,
                    significance=significance,
                    velocity=velocity,
                    acceleration=acceleration,
                )
            )

        aggregate_momentum = sum(f.momentum_score for f in flows) / max(len(flows), 1)

        return FlowReport(
            initial_snapshot=initial_snapshot,
            latest_snapshot=latest_snapshot,
            flows=flows,
            time_delta=time_delta,
            aggregate_momentum=aggregate_momentum,
        )


__all__ = [
    "FlowDirection",
    "TrueProbabilityResult",
    "BayesianPrior",
    "BayesianPosterior",
    "FlowResult",
    "FlowReport",
    "Glicko2Rating",
    "ProbabilityEngine",
]
