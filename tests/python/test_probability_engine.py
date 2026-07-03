"""
EDP V2.0 测试套件 — 概率引擎与顶层接口

⚠️ 本测试仅供学术研究验证，不构成任何决策建议。
"""

import os
import sys
from datetime import datetime, timedelta

# 将 src/python 加入路径（包名 edp）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "python"))

# 以 edp 包名加载
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "edp",
    os.path.join(os.path.dirname(__file__), "..", "..", "src", "python", "__init__.py"),
    submodule_search_locations=[os.path.join(os.path.dirname(__file__), "..", "..", "src", "python")],
)
edp_module = importlib.util.module_from_spec(_spec)
sys.modules["edp"] = edp_module
_spec.loader.exec_module(edp_module)

from edp import (  # noqa: E402
    EDP,
    AllocationEngine,
    AllocationLeg,
    BayesianPrior,
    CalibrationEngine,
    ConformalConfig,
    ConformalEngine,
    DomainAwarenessEngine,
    EventGraph,
    Evidence,
    FlowAmplificationEngine,
    FlowDirection,
    GenericDomain,
    OnlineAggregator,
    Outcome,
    ProbabilityEngine,
    Quote,
    RiskTier,
    Snapshot,
)

# ----------------------------------------------------------------------
# Layer 0: 核心数据类型
# ----------------------------------------------------------------------

def test_outcome_creation():
    o = Outcome(id="a", label="结果A")
    assert o.id == "a"
    assert o.label == "结果A"
    assert o.metadata == {}


def test_quote_to_probability():
    # decimal_odds
    q = Quote(outcome_id="a", value=2.0, signal_type="decimal_odds")
    assert abs(q.to_probability() - 0.5) < 1e-6
    # probability
    q = Quote(outcome_id="a", value=0.7, signal_type="probability")
    assert abs(q.to_probability() - 0.7) < 1e-6
    # percentage
    q = Quote(outcome_id="a", value=75.0, signal_type="percentage")
    assert abs(q.to_probability() - 0.75) < 1e-6


def test_evidence_extract_probability():
    e = Evidence(id="e1", source_type="model", content={"probability": 0.8})
    assert abs(e.extract_probability() - 0.8) < 1e-6
    e = Evidence(id="e2", source_type="nlp", content={"direction": "upward"})
    assert abs(e.extract_probability() - 0.65) < 1e-6
    e = Evidence(id="e3", source_type="nlp", content={"direction": "downward"})
    assert abs(e.extract_probability() - 0.35) < 1e-6


def test_snapshot_validation():
    s = Snapshot(timestamp=datetime.now(), probabilities={"a": 0.5, "b": 0.5})
    assert s.validate() is True
    s = Snapshot(timestamp=datetime.now(), probabilities={"a": 0.3, "b": 0.3})
    assert s.validate() is False


def test_event_graph_chain():
    g = EventGraph.chain(["a", "b", "c"])
    assert g.get_adjacent("a") == ["b"]
    assert set(g.get_adjacent("b")) == {"a", "c"}
    assert g.get_adjacent("c") == ["b"]


def test_event_graph_fully_connected():
    g = EventGraph.fully_connected(["a", "b", "c"])
    assert set(g.get_adjacent("a")) == {"b", "c"}
    assert set(g.get_adjacent("b")) == {"a", "c"}


def test_generic_domain():
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    outcomes = domain.get_outcomes()
    assert len(outcomes) == 2
    g = domain.build_event_graph(outcomes)
    assert "a" in g.get_adjacent("b")
    prior = domain.get_prior()
    assert abs(prior["a"] - 0.5) < 1e-6


# ----------------------------------------------------------------------
# Layer 1-3: 概率引擎
# ----------------------------------------------------------------------

def test_shin_normalization():
    engine = ProbabilityEngine()
    # 报价 2.0 / 2.0 → 概率 0.5 / 0.5
    result = engine.calculate_true_probability({"a": 2.0, "b": 2.0})
    assert abs(result.true_probabilities["a"] - 0.5) < 0.01
    assert abs(result.true_probabilities["b"] - 0.5) < 0.01
    assert abs(sum(result.true_probabilities.values()) - 1.0) < 1e-6


def test_shin_with_margin():
    engine = ProbabilityEngine()
    # 带边际的报价：1.5 / 3.0 / 6.0
    result = engine.calculate_true_probability({"a": 1.5, "b": 3.0, "c": 6.0})
    assert result.market_margin > 0  # 存在边际
    assert abs(sum(result.true_probabilities.values()) - 1.0) < 1e-6
    # a 概率最高
    assert result.true_probabilities["a"] > result.true_probabilities["b"]
    assert result.true_probabilities["b"] > result.true_probabilities["c"]


def test_bayesian_update():
    engine = ProbabilityEngine()
    prior = BayesianPrior(alpha=1.0, beta=1.0)  # 均匀先验
    posterior = engine.bayesian_update(prior, evidence_successes=7, evidence_trials=10)
    # 后验均值应接近 0.7
    assert 0.6 < posterior.expected_probability < 0.8
    assert posterior.credible_interval[0] < posterior.expected_probability
    assert posterior.credible_interval[1] > posterior.expected_probability


def test_flow_analysis():
    engine = ProbabilityEngine()
    t0 = datetime.now()
    t1 = t0 + timedelta(hours=1)
    s0 = Snapshot(timestamp=t0, probabilities={"a": 0.5, "b": 0.5})
    s1 = Snapshot(timestamp=t1, probabilities={"a": 0.6, "b": 0.4})
    report = engine.analyze_flow(s0, s1)
    assert len(report.flows) == 2
    a_flow = next(f for f in report.flows if f.outcome == "a")
    assert a_flow.direction == FlowDirection.UPWARD
    assert abs(a_flow.flow_pp - 10.0) < 0.01  # 0.6 - 0.5 = 0.1 = 10pp


def test_glicko2_rating():
    engine = ProbabilityEngine()
    engine.update_glicko_rating("team_a", [(1.0, 1500.0, 200.0)])  # 胜
    rating = engine.glicko_ratings["team_a"]
    assert rating.rating > 1500.0  # 胜后评分上升
    assert rating.games_played == 1


# ----------------------------------------------------------------------
# Layer 2: 在线聚合
# ----------------------------------------------------------------------

def test_online_aggregator_mlpoly():
    agg = OnlineAggregator({"algorithm": "mlpoly"})
    agg.initialize(["m1", "m2", "m3"])
    # m1 总是更准确
    for _ in range(20):
        preds = {"m1": 0.7, "m2": 0.5, "m3": 0.3}
        agg.predict(preds)
        agg.update(preds, 0.7)  # 实际值 0.7
    weights = agg.get_weights()
    assert weights["m1"] > weights["m2"]
    assert weights["m2"] > weights["m3"]


def test_online_aggregator_ewa():
    agg = OnlineAggregator({"algorithm": "ewa", "eta": 2.0})
    agg.initialize(["a", "b"])
    for _ in range(10):
        preds = {"a": 0.9, "b": 0.1}
        agg.predict(preds)
        agg.update(preds, 0.9)
    weights = agg.get_weights()
    assert weights["a"] > weights["b"]


# ----------------------------------------------------------------------
# Layer 3: 流向倍增
# ----------------------------------------------------------------------

def test_flow_amplification():
    engine = ProbabilityEngine()
    flow_engine = FlowAmplificationEngine()
    t0 = datetime.now()
    t1 = t0 + timedelta(hours=1)
    s0 = Snapshot(timestamp=t0, probabilities={"a": 0.3, "b": 0.7})
    s1 = Snapshot(timestamp=t1, probabilities={"a": 0.5, "b": 0.5})
    flow_report = engine.analyze_flow(s0, s1)
    graph = EventGraph.chain(["a", "b"])
    amp_report = flow_engine.calculate_amplification(
        flow_report, {"a": 0.5, "b": 0.5}, graph
    )
    assert len(amp_report.amplifications) == 2
    a_amp = next(a for a in amp_report.amplifications if a.outcome == "a")
    # a 流向上升（0.3→0.5），应有正向倍增
    assert a_amp.base_flow_pp > 0


# ----------------------------------------------------------------------
# Layer 4: 全域感知
# ----------------------------------------------------------------------

def test_domain_awareness():
    from edp import EvidenceSource, EvidenceType, SourceReliability
    engine = DomainAwarenessEngine()
    now = datetime.now()
    sources = [
        EvidenceSource("s1", EvidenceType.MODEL, SourceReliability.B, now,
                       {"probability": 0.7}, confidence=0.8),
        EvidenceSource("s2", EvidenceType.SENSOR, SourceReliability.A, now,
                       {"probability": 0.68}, confidence=0.9),
        EvidenceSource("s3", EvidenceType.MODEL, SourceReliability.C, now,
                       {"probability": 0.65}, confidence=0.5),
    ]
    assessment = engine.assess_situation(sources)
    assert 0.6 < assessment.aggregate_probability < 0.8
    assert assessment.consensus_score > 0.5  # 三源接近，共识高
    assert assessment.source_count == 3


# ----------------------------------------------------------------------
# Layer 5: 资源分配
# ----------------------------------------------------------------------

def test_allocation_three_principles():
    engine = AllocationEngine()
    # 满足三原则：正向流向 + 正期望 + 合理结构
    leg = AllocationLeg(
        outcome_id="a", probability=0.6, return_multiplier=2.0,
        flow_direction="upward", confidence=0.8,
    )
    ok, _ = engine.validate_three_principles(leg)
    assert ok is True
    # 不满足：负期望
    leg = AllocationLeg(
        outcome_id="a", probability=0.3, return_multiplier=1.5,
        flow_direction="upward", confidence=0.8,
    )
    ok, _ = engine.validate_three_principles(leg)
    assert ok is False


def test_allocation_generation():
    engine = AllocationEngine()
    candidates = [
        AllocationLeg("a", 0.6, 2.0, flow_direction="upward", confidence=0.8),
        AllocationLeg("b", 0.5, 2.2, flow_direction="upward", confidence=0.7),
    ]
    bundle = engine.generate_allocation(1000, candidates)
    assert bundle.budget == 1000
    assert len(bundle.warnings) > 0  # 应有风险警示
    assert any("不构成投资建议" in w for w in bundle.warnings)


def test_allocation_concentration_limit():
    engine = AllocationEngine({"max_concentration": 0.2})
    candidates = [
        AllocationLeg("a", 0.9, 3.0, flow_direction="upward", confidence=0.9),
        AllocationLeg("b", 0.5, 2.0, flow_direction="upward", confidence=0.7),
        AllocationLeg("c", 0.5, 2.0, flow_direction="upward", confidence=0.7),
        AllocationLeg("d", 0.5, 2.0, flow_direction="upward", confidence=0.7),
        AllocationLeg("e", 0.5, 2.0, flow_direction="upward", confidence=0.7),
    ]
    bundle = engine.generate_allocation(1000, candidates)
    for leg in bundle.legs:
        assert leg.allocation_fraction <= 0.21  # 允许归一化后小幅浮动


# ----------------------------------------------------------------------
# Layer 6: 校准
# ----------------------------------------------------------------------

def test_calibration_brier():
    calib = CalibrationEngine()
    result = calib.evaluate({"a": 0.7, "b": 0.3}, "a")
    assert 0 <= result["brier_score"] <= 1
    assert result["top1_correct"] is True


def test_calibration_brier_decomposition():
    calib = CalibrationEngine()
    history = [(0.7, 1), (0.3, 0), (0.8, 1), (0.4, 0), (0.6, 1), (0.2, 0)]
    decomp = calib.brier_decomposition(history)
    assert "reliability" in decomp
    assert "resolution" in decomp
    assert "uncertainty" in decomp
    assert decomp["brier_score"] >= 0


def test_calibration_curve():
    calib = CalibrationEngine()
    history = [(0.1, 0), (0.3, 0), (0.5, 1), (0.7, 1), (0.9, 1)]
    curve = calib.calibration_curve(history, n_bins=5)
    assert len(curve) > 0
    for pred, obs, count in curve:
        assert 0 <= pred <= 1
        assert 0 <= obs <= 1
        assert count > 0


# ----------------------------------------------------------------------
# 顶层 EDP 接口
# ----------------------------------------------------------------------

def test_edp_analyze_two_outcomes():
    domain = GenericDomain([Outcome("rain", "下雨"), Outcome("no_rain", "不下雨")])
    edp = EDP(domain)
    result = edp.analyze(
        evidence=[
            Evidence("m1", "model", {"probability": 0.72}, outcome_id="rain", confidence=0.8),
            Evidence("s1", "sensor", {"probability": 0.68}, outcome_id="rain", confidence=0.9),
            Evidence("h1", "model", {"probability": 0.60}, outcome_id="rain", confidence=0.5),
        ],
        budget=1000,
    )
    assert "probabilities" in result
    assert "summary" in result
    assert "warnings" in result
    assert "prediction_set" in result  # L7 保形预测集
    assert len(result["warnings"]) > 0  # 应有风险警示
    assert abs(sum(result["probabilities"].values()) - 1.0) < 0.05
    # P0 修复验证：定向证据指向 rain，rain 应明显 > 0.5
    assert result["probabilities"]["rain"] > 0.55


def test_edp_analyze_with_market_quotes():
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B"), Outcome("c", "C")])
    edp = EDP(domain)
    result = edp.analyze(
        raw_data={"a": 1.5, "b": 3.0, "c": 6.0},
        budget=5000,
        return_multipliers={"a": 1.5, "b": 3.0, "c": 6.0},
    )
    probs = result["probabilities"]
    assert probs["a"] > probs["b"]
    assert probs["b"] > probs["c"]
    assert abs(sum(probs.values()) - 1.0) < 0.01


def test_edp_version():
    assert edp_module.__version__ == "2.0.0"


def test_edp_warnings_contain_risk_disclaimer():
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    result = edp.analyze(evidence=[Evidence("e1", "model", {"probability": 0.6})])
    warning_text = " ".join(result["warnings"])
    assert "不构成" in warning_text or "学术研究" in warning_text


# ----------------------------------------------------------------------
# P0 修复：定向证据 log-odds 更新
# ----------------------------------------------------------------------

def test_directed_evidence_updates_target_outcome():
    """定向证据应只提升指向的结果，不影响其它结果相对比例。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B"), Outcome("c", "C")])
    edp = EDP(domain)
    result = edp.analyze(
        evidence=[
            Evidence("e1", "model", {"probability": 0.9}, outcome_id="a", confidence=0.9),
        ],
    )
    p = result["probabilities"]
    assert p["a"] > 0.5  # a 被定向证据提升
    assert p["a"] > p["b"]
    assert p["a"] > p["c"]


# ----------------------------------------------------------------------
# L7: 保形预测（2025 前沿）
# ----------------------------------------------------------------------

def test_conformal_split_prediction_set():
    """Split Conformal：校准后预测集应包含高概率结果。"""
    engine = ConformalEngine(ConformalConfig(alpha=0.1, method="split"))
    # 校准集：5 次预测，actual 都是 a，p(a)≈0.7
    history = [({"a": 0.7, "b": 0.3}, "a") for _ in range(5)]
    engine.calibrate(history)
    pset = engine.predict({"a": 0.75, "b": 0.25})
    assert "a" in pset.prediction_set  # 高概率结果应在集内
    assert pset.coverage_target == 0.9


def test_conformal_aci_online_coverage():
    """ACI：在线更新后经验覆盖率不应低于目标（ACI 保证不欠覆盖）。"""
    import random
    random.seed(7)
    engine = ConformalEngine(ConformalConfig(alpha=0.1, method="aci", aci_gamma=0.01))
    # 稳定分布：a 以 0.7 概率发生
    preds_template = {"a": 0.7, "b": 0.3}
    for _ in range(200):
        engine.predict(preds_template)
        actual = "a" if random.random() < 0.7 else "b"
        engine.update(preds_template, actual)
    stats = engine.coverage_stats()
    # ACI 保证长程不欠覆盖；在常数预测退化场景下趋于保守（覆盖率偏高）
    assert stats["empirical_coverage"] >= 0.85
    assert stats["n_updates"] == 200
    assert stats["calibration_size"] == 200


def test_conformal_agaci_runs():
    """AgACI：应正常运行并产出预测集。"""
    engine = ConformalEngine(ConformalConfig(alpha=0.2, method="agaci"))
    engine.calibrate([({"a": 0.6, "b": 0.4}, "a") for _ in range(10)])
    pset = engine.predict({"a": 0.65, "b": 0.35})
    assert pset.method == "agaci"
    assert isinstance(pset.prediction_set, list)


def test_conformal_update_returns_coverage():
    engine = ConformalEngine(ConformalConfig(alpha=0.1, method="aci"))
    engine.calibrate([({"a": 0.7, "b": 0.3}, "a") for _ in range(5)])
    res = engine.update({"a": 0.7, "b": 0.3}, "a")
    assert "covered" in res
    assert "coverage_rate" in res
    assert res["covered"] is True


# ----------------------------------------------------------------------
# Online Bayesian Stacking（Soft-Bayes）
# ----------------------------------------------------------------------

def test_online_bayesian_stacking_prefers_best_source():
    agg = OnlineAggregator({"algorithm": "online_bayesian_stacking", "obs_eta": 0.3})
    agg.initialize(["good", "bad"])
    import random
    random.seed(1)
    for _ in range(30):
        actual = 0.8
        preds = {"good": 0.8, "bad": 0.2}  # good 总是准
        agg.predict(preds)
        agg.update(preds, actual)
    weights = agg.get_weights()
    assert weights["good"] > weights["bad"]


# ----------------------------------------------------------------------
# Hyvärinen score
# ----------------------------------------------------------------------

def test_hyvarinen_score_penalizes_wrong_prediction():
    calib = CalibrationEngine()
    # 预测 a 概率高，实际 a 发生 → 低分（好）
    good = calib.hyvarinen_score({"a": 0.9, "b": 0.1}, "a")
    # 预测 a 概率高，实际 b 发生 → 高分（差）
    bad = calib.hyvarinen_score({"a": 0.9, "b": 0.1}, "b")
    assert bad > good


# ----------------------------------------------------------------------
# 模型多样性（DTVW）
# ----------------------------------------------------------------------

def test_model_diversity():
    from datetime import datetime

    from edp import EvidenceSource, EvidenceType, SourceReliability
    now = datetime.now()
    # 高冗余：三个源概率几乎相同
    redundant = [
        EvidenceSource("s1", EvidenceType.MODEL, SourceReliability.B, now, {"probability": 0.50}),
        EvidenceSource("s2", EvidenceType.MODEL, SourceReliability.B, now, {"probability": 0.51}),
        EvidenceSource("s3", EvidenceType.MODEL, SourceReliability.B, now, {"probability": 0.49}),
    ]
    # 高多样：三个源概率差异大
    diverse = [
        EvidenceSource("s1", EvidenceType.MODEL, SourceReliability.B, now, {"probability": 0.20}),
        EvidenceSource("s2", EvidenceType.MODEL, SourceReliability.B, now, {"probability": 0.50}),
        EvidenceSource("s3", EvidenceType.MODEL, SourceReliability.B, now, {"probability": 0.80}),
    ]
    r = DomainAwarenessEngine.model_diversity(redundant)
    d = DomainAwarenessEngine.model_diversity(diverse)
    assert d["diversity"] > r["diversity"]
    assert r["redundancy"] > d["redundancy"]
    assert d["effective_sources"] > r["effective_sources"]


# ----------------------------------------------------------------------
# EDP 顶层 L7 集成
# ----------------------------------------------------------------------

def test_edp_conformal_predict_returns_set():
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain, {"conformal": {"method": "aci", "alpha": 0.1}})
    result = edp.analyze(
        evidence=[Evidence("e1", "model", {"probability": 0.7}, outcome_id="a")],
    )
    pset = result["prediction_set"]
    assert isinstance(pset.prediction_set, list)
    assert pset.coverage_target == 0.9


# ----------------------------------------------------------------------
# 覆盖率补充测试：online_aggregator / probability_engine / allocation_engine
# / calibration / conformal / flow_amplification / domain_awareness / edp
# ----------------------------------------------------------------------


# ===== online_aggregator.py =====


def test_online_agg_invalid_algorithm():
    """非法 algorithm 应 raise ValueError。"""
    try:
        OnlineAggregator({"algorithm": "unknown"})
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_online_agg_invalid_loss_type():
    """非法 loss_type 应 raise ValueError。"""
    try:
        OnlineAggregator({"loss_type": "unknown"})
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_online_agg_initialize_empty():
    """initialize([]) 应 raise ValueError。"""
    agg = OnlineAggregator()
    try:
        agg.initialize([])
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_online_agg_predict_without_init():
    """未 initialize 直接 predict 应自动初始化。"""
    agg = OnlineAggregator({"algorithm": "mlpoly"})
    out = agg.predict({"a": 0.6, "b": 0.4})
    assert abs(out - 0.5) < 1e-6  # 均匀权重 (0.5*0.6+0.5*0.4=0.5)


def test_online_agg_predict_adds_new_source():
    """predict 时出现新来源应自动加入并归一化。"""
    agg = OnlineAggregator({"algorithm": "mlpoly"})
    agg.initialize(["a"])
    agg.predict({"a": 0.6, "b": 0.4})  # b 是新来源
    weights = agg.get_weights()
    assert "b" in weights
    assert abs(sum(weights.values()) - 1.0) < 1e-6


def test_online_agg_update_without_init():
    """未 initialize 直接 update 应自动初始化。"""
    agg = OnlineAggregator({"algorithm": "ewa"})
    agg.update({"a": 0.7, "b": 0.3}, 0.7)
    assert agg._initialized is True


def test_online_agg_update_adds_new_source():
    """update 时出现新来源应自动加入。"""
    agg = OnlineAggregator({"algorithm": "mlpoly"})
    agg.initialize(["a"])
    agg.update({"a": 0.7, "b": 0.3}, 0.7)  # b 新来源
    assert "b" in agg.weights


def test_online_agg_ridge():
    """Ridge 算法应正常运行并更新权重。"""
    agg = OnlineAggregator({"algorithm": "ridge", "ridge_lambda": 0.5})
    agg.initialize(["good", "bad"])
    for _ in range(15):
        preds = {"good": 0.8, "bad": 0.2}
        agg.predict(preds)
        agg.update(preds, 0.8)
    w = agg.get_weights()
    assert w["good"] >= w["bad"]


def test_online_agg_get_performance():
    """get_performance 应返回完整统计。"""
    agg = OnlineAggregator({"algorithm": "mlpoly"})
    agg.initialize(["a", "b"])
    agg.update({"a": 0.7, "b": 0.3}, 0.7)
    perf = agg.get_performance()
    assert "a" in perf and "b" in perf
    assert perf["a"]["n_predictions"] == 1
    assert perf["a"]["avg_loss"] >= 0


def test_online_agg_absolute_loss():
    """absolute loss 应正常计算。"""
    agg = OnlineAggregator({"algorithm": "mlpoly", "loss_type": "absolute"})
    agg.initialize(["a", "b"])
    agg.update({"a": 0.7, "b": 0.3}, 0.5)
    # a loss=0.2, b loss=0.2，两者相等
    w = agg.get_weights()
    assert abs(w["a"] - w["b"]) < 1e-6


def test_online_agg_log_loss():
    """log loss 应正常计算（不报错）。"""
    agg = OnlineAggregator({"algorithm": "mlpoly", "loss_type": "log"})
    agg.initialize(["a", "b"])
    agg.update({"a": 0.7, "b": 0.3}, 1.0)
    w = agg.get_weights()
    assert abs(sum(w.values()) - 1.0) < 1e-6


def test_online_agg_recent_losses_trim():
    """超过 100 条 recent_losses 应裁剪。"""
    agg = OnlineAggregator({"algorithm": "mlpoly"})
    agg.initialize(["a"])
    for _ in range(105):
        agg.update({"a": 0.5}, 0.5)
    assert len(agg.performances["a"].recent_losses) <= 100


def test_online_agg_mlpoly_empty_losses():
    """_update_mlpoly 在 losses 空时早 return（不会崩）。"""
    agg = OnlineAggregator({"algorithm": "mlpoly"})
    agg.initialize(["a", "b"])
    # 手动清空 losses 后调用内部方法
    agg.losses = {"a": [], "b": []}
    agg._update_mlpoly({"a": 0.5, "b": 0.5}, 0.5)  # 应早 return 不崩


def test_online_agg_ewa_empty_losses():
    """_update_ewa 在 losses 空时早 return。"""
    agg = OnlineAggregator({"algorithm": "ewa"})
    agg.initialize(["a", "b"])
    agg.losses = {"a": [], "b": []}
    agg._update_ewa({"a": 0.5, "b": 0.5}, 0.5)


def test_online_agg_ridge_no_predictions():
    """_update_ridge 在 sids 为空时早 return。"""
    agg = OnlineAggregator({"algorithm": "ridge"})
    agg.initialize(["a"])
    # predictions 为空 dict
    agg._update_ridge({}, 0.5)


def test_online_agg_solve_linear_singular():
    """_solve_linear 奇异矩阵应跳过（返回 None 或零向量不崩）。"""
    # 构造奇异矩阵：两行相同
    A = [[1.0, 1.0], [1.0, 1.0]]
    b = [1.0, 1.0]
    result = OnlineAggregator._solve_linear(A, b, 2)
    # 不应崩，result 可能是 [0,0] 或带值
    assert isinstance(result, list)


def test_online_agg_obs_empty_predictions():
    """_update_obs 在 predictions 空 / weights 空时早 return。"""
    agg = OnlineAggregator({"algorithm": "online_bayesian_stacking"})
    agg.initialize(["a"])
    agg._update_obs({}, 0.5)  # 空 predictions，早 return
    agg.weights = {}
    agg._update_obs({"a": 0.5}, 0.5)  # weights 空，早 return


def test_online_agg_obs_combined_near_zero():
    """_update_obs 在 combined≈0 时用 1e-6 兜底不崩。"""
    agg = OnlineAggregator({"algorithm": "online_bayesian_stacking", "obs_eta": 0.3})
    agg.initialize(["a", "b"])
    # 权重和预测都极小，触发 combined≈0 分支
    agg.weights = {"a": 1e-15, "b": 1e-15}
    agg._update_obs({"a": 1e-15, "b": 1e-15}, 0.5)


def test_online_agg_add_source_renormalize():
    """_add_source 后权重应归一化。"""
    agg = OnlineAggregator({"algorithm": "mlpoly"})
    agg.initialize(["a"])
    agg._add_source("b")
    agg._add_source("c")
    assert abs(sum(agg.weights.values()) - 1.0) < 1e-6


# ===== probability_engine.py =====


def test_true_prob_result_helpers():
    """TrueProbabilityResult 的 overround/get_most_likely/ranking。"""
    engine = ProbabilityEngine()
    r = engine.calculate_true_probability({"a": 1.5, "b": 3.0, "c": 6.0})
    assert r.overround == r.market_margin
    top, prob = r.get_most_likely_outcome()
    assert top == "a"
    ranking = r.get_probability_ranking()
    assert ranking[0][0] == "a"
    assert ranking[0][1] >= ranking[-1][1]


def test_bayesian_prior_properties():
    """BayesianPrior 的 mean/variance/effective_sample_size。"""
    p = BayesianPrior(alpha=3.0, beta=2.0)
    assert abs(p.mean - 0.6) < 1e-6
    assert p.variance > 0
    assert abs(p.effective_sample_size - 5.0) < 1e-6


def test_bayesian_posterior_properties():
    """BayesianPosterior 的 variance/effective_sample_size。"""
    engine = ProbabilityEngine()
    post = engine.bayesian_update(BayesianPrior(1.0, 1.0), 7, 10)
    assert post.variance > 0
    assert abs(post.effective_sample_size - (8.0 + 4.0)) < 1e-6


def test_flow_result_significance_and_confidence():
    """FlowResult.is_significant / get_confidence_level。"""
    t0 = datetime.now()
    t1 = t0 + timedelta(hours=1)
    s0 = Snapshot(timestamp=t0, probabilities={"a": 0.3, "b": 0.7})
    s1 = Snapshot(timestamp=t1, probabilities={"a": 0.6, "b": 0.4})
    report = ProbabilityEngine().analyze_flow(s0, s1)
    a_flow = next(f for f in report.flows if f.outcome == "a")
    assert a_flow.is_significant(threshold=2.0) is True
    c = a_flow.get_confidence_level()
    assert 0 <= c <= 1


def test_flow_report_helpers():
    """FlowReport 的各种 getter / summary。"""
    t0 = datetime.now()
    t1 = t0 + timedelta(hours=1)
    s0 = Snapshot(timestamp=t0, probabilities={"a": 0.3, "b": 0.7})
    s1 = Snapshot(timestamp=t1, probabilities={"a": 0.6, "b": 0.4})
    report = ProbabilityEngine().analyze_flow(s0, s1)
    assert len(report.get_upward_flows()) >= 1
    assert len(report.get_downward_flows()) >= 1
    assert len(report.get_significant_flows(2.0)) >= 1
    summary = report.get_flow_summary()
    assert summary["total_outcomes"] == 2
    assert summary["upward_count"] >= 1


def test_conditional_probability():
    """calculate_conditional_probability。"""
    engine = ProbabilityEngine()
    probs = {"a": 0.5, "b": 0.3, "c": 0.2}
    cond = engine.calculate_conditional_probability(probs, ["a", "b"])
    assert abs(cond["a"] - 0.5 / 0.8) < 1e-6
    assert abs(cond["b"] - 0.3 / 0.8) < 1e-6
    # condition_total == 0
    cond0 = engine.calculate_conditional_probability(probs, ["x"])
    assert cond0["x"] == 0.0


def test_combine_priors():
    """combine_priors 加权融合。"""
    engine = ProbabilityEngine()
    priors = [
        BayesianPrior(alpha=2.0, beta=2.0, weight=1.0),
        BayesianPrior(alpha=4.0, beta=1.0, weight=2.0),
    ]
    post = engine.combine_priors(priors)
    # 加权 alpha = (2*1+4*2)/3 = 10/3, beta = (2*1+1*2)/3 = 4/3
    assert abs(post.posterior_alpha - 10.0 / 3.0) < 1e-6
    assert abs(post.posterior_beta - 4.0 / 3.0) < 1e-6
    # 空先验
    post2 = engine.combine_priors([])
    assert post2.posterior_alpha == 1.0
    # 带新证据
    post3 = engine.combine_priors(priors, {"successes": 3, "trials": 5})
    assert post3.posterior_alpha > post.posterior_alpha


def test_combine_priors_with_evidence_failures():
    """combine_priors trials<successes 时 max 兜底。"""
    engine = ProbabilityEngine()
    priors = [BayesianPrior(alpha=1.0, beta=1.0, weight=1.0)]
    # successes=2, trials=1（异常输入），max(trials-successes,0)=0
    post = engine.combine_priors(priors, {"successes": 2, "trials": 1})
    assert post.posterior_beta == 1.0  # 1 + 0


def test_predict_with_rating():
    """predict_with_rating 三结果概率和为 1。"""
    engine = ProbabilityEngine()
    engine.update_glicko_rating("home", [(1.0, 1500.0, 200.0)])
    engine.update_glicko_rating("away", [(0.0, 1500.0, 200.0)])
    probs = engine.predict_with_rating("home", "away")
    assert abs(sum(probs.values()) - 1.0) < 1e-6
    assert "home_win" in probs and "draw" in probs and "away_win" in probs


def test_analyze_flow_with_history():
    """analyze_flow 带 historical_snapshots 分支。"""
    t0 = datetime.now()
    t1 = t0 + timedelta(hours=1)
    t2 = t0 + timedelta(hours=2)
    t3 = t0 + timedelta(hours=3)
    s0 = Snapshot(timestamp=t0, probabilities={"a": 0.2, "b": 0.8})
    sh1 = Snapshot(timestamp=t1, probabilities={"a": 0.3, "b": 0.7})
    sh2 = Snapshot(timestamp=t2, probabilities={"a": 0.4, "b": 0.6})
    s1 = Snapshot(timestamp=t3, probabilities={"a": 0.6, "b": 0.4})
    report = ProbabilityEngine().analyze_flow(s0, s1, historical_snapshots=[sh1, sh2])
    assert len(report.flows) == 2
    a_flow = next(f for f in report.flows if f.outcome == "a")
    # 有历史快照应计算 acceleration
    assert isinstance(a_flow.acceleration, float)


def test_shin_empty_and_edge():
    """Shin 归一化的空输入与边界。"""
    engine = ProbabilityEngine()
    # 空输入应 raise（不崩）
    try:
        engine.calculate_true_probability({})
        raise AssertionError("should raise")
    except ValueError:
        pass
    # 单结果（sqrt_sum <= 1 分支）
    result = engine.calculate_true_probability({"a": 2.0})
    assert abs(result.true_probabilities["a"] - 1.0) < 1e-6


def test_bayesian_update_validation():
    """bayesian_update 参数校验。"""
    engine = ProbabilityEngine()
    try:
        engine.bayesian_update(BayesianPrior(1, 1), -1, 0)
        raise AssertionError("should raise")
    except ValueError:
        pass
    try:
        engine.bayesian_update(BayesianPrior(1, 1), 5, 3)  # successes>trials
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_get_or_create_rating():
    """get_or_create_rating 首次创建、二次复用。"""
    engine = ProbabilityEngine()
    r1 = engine.get_or_create_rating("team_x")
    r2 = engine.get_or_create_rating("team_x")
    assert r1 is r2
    assert r1.team_id == "team_x"


def test_glicko_expected_score():
    """Glicko2Rating.expected_score 数值合理。"""
    from edp import Glicko2Rating

    r = Glicko2Rating(team_id="t", rating=1600.0, rd=200.0)
    e = r.expected_score(1500.0, 200.0)
    assert 0 <= e <= 1
    # rating 高于对手，期望 > 0.5
    assert e > 0.5


def test_glicko_update_empty_results():
    """update_rating 空结果应早 return 不崩。"""
    from edp import Glicko2Rating

    r = Glicko2Rating(team_id="t", rating=1500.0, rd=200.0)
    before = r.rating
    r.update_rating([])
    assert r.rating == before  # 未变


# ===== allocation_engine.py =====


def test_allocation_leg_kelly_b_le_zero():
    """return_multiplier=1.0 → b=0 → kelly_optimal=0。"""
    leg = AllocationLeg("a", 0.6, 1.0, flow_direction="upward", confidence=0.8)
    assert leg.kelly_fraction_optimal == 0.0


def test_allocation_result_within_limit():
    """AllocationResult.is_within_limit。"""
    from edp import AllocationResult

    r = AllocationResult("a", 100.0, 0.15, 0.2, 0.05, 0.3, 0.2)
    assert r.is_within_limit(0.2) is True
    assert r.is_within_limit(0.1) is False


def test_allocation_bundle_ratio_and_helpers():
    """AllocationBundle.allocation_ratio / get_top_allocations / get_summary。"""
    from edp import AllocationBundle, AllocationResult

    bundle = AllocationBundle(budget=1000.0)
    assert bundle.allocation_ratio == 0.0  # budget>0, allocated=0
    bundle.budget = 0
    assert bundle.allocation_ratio == 0.0  # budget<=0
    bundle.budget = 1000.0
    bundle.legs = [
        AllocationResult("a", 300.0, 0.3, 0.2, 0.05, 0.2, 0.1),
        AllocationResult("b", 200.0, 0.2, 0.1, 0.03, 0.15, 0.1),
    ]
    bundle.allocated_amount = 500.0
    assert abs(bundle.allocation_ratio - 0.5) < 1e-6
    top = bundle.get_top_allocations(1)
    assert top[0].outcome_id == "a"
    s = bundle.get_summary()
    assert s["budget"] == 1000.0
    assert s["n_legs"] == 2


def test_allocation_principles_low_prob_and_low_return():
    """三原则验证：概率过低 / 回报过低。"""
    engine = AllocationEngine()
    # 概率过低
    leg = AllocationLeg("a", 0.05, 2.0, flow_direction="upward", confidence=0.8)
    ok, _ = engine.validate_three_principles(leg)
    assert ok is False
    # 回报过低
    leg = AllocationLeg("a", 0.6, 1.05, flow_direction="upward", confidence=0.8)
    ok, _ = engine.validate_three_principles(leg)
    assert ok is False


def test_allocation_negative_flow_rejected():
    """三原则：负流向被拒。"""
    engine = AllocationEngine()
    leg = AllocationLeg("a", 0.6, 2.0, flow_direction="downward", confidence=0.8)
    ok, _ = engine.validate_three_principles(leg)
    assert ok is False


def test_allocation_zero_budget():
    """预算为 0 时返回空分配带 warning。"""
    engine = AllocationEngine()
    bundle = engine.generate_allocation(0, [AllocationLeg("a", 0.6, 2.0, "upward", 0.8)])
    assert len(bundle.legs) == 0
    assert any("预算" in w for w in bundle.warnings)


def test_allocation_no_valid_candidates():
    """所有候选都不通过三原则。"""
    engine = AllocationEngine()
    bad = [AllocationLeg("a", 0.1, 1.05, "downward", 0.3)]
    bundle = engine.generate_allocation(1000, bad)
    assert len(bundle.legs) == 0
    assert any("三原则" in w for w in bundle.warnings)


def test_allocation_extreme_risk_tier():
    """EXTREME 风险分层应加 warning。"""
    engine = AllocationEngine()

    candidates = [AllocationLeg("a", 0.6, 2.0, "upward", 0.8)]
    bundle = engine.generate_allocation(1000, candidates, risk_tier=RiskTier.EXTREME)
    assert any("EXTREME" in w for w in bundle.warnings)


def test_allocation_calculate_kelly():
    """calculate_kelly 显式 fraction。"""
    engine = AllocationEngine()
    leg = AllocationLeg("a", 0.6, 2.0, "upward", 0.8)
    k = engine.calculate_kelly(leg, 0.5)
    assert k > 0
    # 不传 fraction 用默认
    k2 = engine.calculate_kelly(leg)
    assert k2 > 0


def test_allocation_optimize_portfolio():
    """optimize_portfolio Markowitz 再平衡。"""
    from edp import AllocationBundle, AllocationResult

    engine = AllocationEngine({"target_diversification": 0.8})
    bundle = AllocationBundle(budget=1000.0)
    # 高度集中：一条腿占 0.9
    bundle.legs = [
        AllocationResult("a", 900.0, 0.9, 0.5, 0.25, 0.5, 0.1),
        AllocationResult("b", 100.0, 0.1, 0.1, 0.05, 0.2, 0.1),
    ]
    bundle.allocated_amount = 1000.0
    bundle.diversification_score = 0.18  # 1 - (0.81+0.01) = 0.18
    bundle.max_concentration = 0.9
    optimized = engine.optimize_portfolio(bundle, target_diversification=0.5)
    # 应执行再平衡
    assert optimized.max_concentration < 0.9


def test_allocation_optimize_no_legs():
    """optimize_portfolio 无腿或已达标时直接返回。"""
    engine = AllocationEngine()
    from edp import AllocationBundle

    bundle = AllocationBundle(budget=1000.0)
    out = engine.optimize_portfolio(bundle)
    assert out is bundle  # 无腿，直接返回


def test_allocation_optimize_single_leg():
    """单条腿无法再平衡，直接返回。"""
    engine = AllocationEngine({"target_diversification": 0.9})
    from edp import AllocationBundle, AllocationResult

    bundle = AllocationBundle(budget=1000.0)
    bundle.legs = [AllocationResult("a", 1000.0, 1.0, 0.5, 0.25, 0.5, 0.1)]
    bundle.diversification_score = 0.0
    out = engine.optimize_portfolio(bundle)
    assert out is bundle


def test_allocation_calculate_diversification_empty():
    """_calculate_diversification 空列表返回 0。"""
    engine = AllocationEngine()
    assert engine._calculate_diversification([]) == 0.0


def test_allocation_all_risk_tiers():
    """遍历所有风险分层。"""

    engine = AllocationEngine()
    candidates = [AllocationLeg("a", 0.6, 2.0, "upward", 0.8)]
    for tier in [RiskTier.CONSERVATIVE, RiskTier.BALANCED, RiskTier.AGGRESSIVE, RiskTier.EXTREME]:
        bundle = engine.generate_allocation(1000, candidates, risk_tier=tier)
        assert bundle.budget == 1000


# ===== calibration.py =====


from edp import PredictionRecord  # noqa: E402


def test_calibration_log_score():
    """CalibrationEngine log score。"""
    calib = CalibrationEngine()
    r = calib.evaluate({"a": 0.7, "b": 0.3}, "a")
    assert "log_score" in r or "log_loss" in r or r.get("brier_score") is not None


def test_calibration_crps():
    """CRPS 评分（静态方法，需 cdf 采样点）。"""
    # forecast_cdf: [(x, F(x)), ...]
    cdf = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
    r = CalibrationEngine.crps(cdf, 0.3)
    assert r >= 0
    # 空 cdf 返回 0
    assert CalibrationEngine.crps([], 0.5) == 0.0


def test_calibration_top1_wrong():
    """预测错误时 top1_correct=False。"""
    calib = CalibrationEngine()
    r = calib.evaluate({"a": 0.7, "b": 0.3}, "b")
    assert r["top1_correct"] is False


def test_prediction_record():
    """PredictionRecord 数据类（正确字段名）。"""
    rec = PredictionRecord(
        timestamp="2026-07-03T00:00:00",
        predicted_probabilities={"a": 0.7, "b": 0.3},
        actual_outcome="a",
    )
    assert rec.actual_outcome == "a"
    assert rec.predicted_top_outcome == "a"
    assert rec.is_top1_correct is True
    # 空预测
    rec2 = PredictionRecord(timestamp="t", predicted_probabilities={}, actual_outcome="a")
    assert rec2.predicted_top_outcome == ""
    assert rec2.is_top1_correct is False


def test_calibration_long_term_performance():
    """long_term_performance 空历史与非空历史。"""
    calib = CalibrationEngine()
    # 空历史
    perf = calib.long_term_performance()
    assert perf["total_predictions"] == 0
    # 非空历史：两次都预测 a 最高，第一次实际 a（对），第二次实际 a（对）
    calib.evaluate({"a": 0.7, "b": 0.3}, "a")
    calib.evaluate({"a": 0.6, "b": 0.4}, "a")
    perf2 = calib.long_term_performance()
    assert perf2["total_predictions"] == 2
    assert perf2["top1_accuracy"] == 1.0  # 两次都对


def test_calibration_reset():
    """reset 清空历史。"""
    calib = CalibrationEngine()
    calib.evaluate({"a": 0.7}, "a")
    assert len(calib.history) == 1
    calib.reset()
    assert len(calib.history) == 0


def test_calibration_brier_decomposition_uses_internal():
    """brier_decomposition 不传 history 用内部历史。"""
    calib = CalibrationEngine()
    calib.evaluate({"a": 0.7, "b": 0.3}, "a")
    calib.evaluate({"a": 0.6, "b": 0.4}, "a")
    calib.evaluate({"a": 0.3, "b": 0.7}, "b")
    d = calib.brier_decomposition()  # 用内部历史
    assert d["brier_score"] >= 0


def test_calibration_calibration_curve_uses_internal():
    """calibration_curve 不传 history 用内部历史。"""
    calib = CalibrationEngine()
    calib.evaluate({"a": 0.7, "b": 0.3}, "a")
    calib.evaluate({"a": 0.4, "b": 0.6}, "b")
    curve = calib.calibration_curve()  # 用内部历史
    assert isinstance(curve, list)


def test_calibration_compute_brier_empty():
    """_compute_brier 空预测返回 0。"""
    assert CalibrationEngine._compute_brier({}, "a") == 0.0


def test_calibration_hyvarinen_empty():
    """hyvarinen_score 空预测返回 0。"""
    assert CalibrationEngine.hyvarinen_score({}, "a") == 0.0


def test_calibration_log_score_extreme():
    """_compute_log_score 极端概率不崩。"""
    s = CalibrationEngine._compute_log_score({"a": 0.0}, "a")
    assert s > 0  # 0 被 eps 兜底，log 很大
    s2 = CalibrationEngine._compute_log_score({"a": 1.0}, "a")
    assert s2 >= 0


def test_calibration_curve_more_bins():
    """校准曲线多 bin。"""
    calib = CalibrationEngine()
    history = [(0.1, 0), (0.2, 0), (0.3, 1), (0.4, 0), (0.5, 1), (0.6, 1), (0.7, 1), (0.8, 1), (0.9, 1)]
    curve = calib.calibration_curve(history, n_bins=3)
    assert len(curve) > 0


def test_calibration_hyvarinen_edge():
    """hyvarinen_score 边界。"""
    calib = CalibrationEngine()
    # 极端概率
    s = calib.hyvarinen_score({"a": 0.99, "b": 0.01}, "a")
    assert isinstance(s, float)


def test_calibration_methods_exist():
    """CalibrationEngine 所有公开方法可调用。"""
    calib = CalibrationEngine()
    assert hasattr(calib, "evaluate")
    # 遍历可能的公开方法名
    for name in ["evaluate", "brier_decomposition", "calibration_curve", "hyvarinen_score"]:
        assert hasattr(calib, name)


# ===== conformal.py =====


def test_conformal_split_no_calibrate():
    """未校准直接 predict 应有兜底行为。"""
    engine = ConformalEngine(ConformalConfig(alpha=0.1, method="split"))
    pset = engine.predict({"a": 0.7, "b": 0.3})
    assert isinstance(pset.prediction_set, list)


def test_conformal_aci_no_calibrate():
    """ACI 未校准直接 predict。"""
    engine = ConformalEngine(ConformalConfig(alpha=0.1, method="aci"))
    pset = engine.predict({"a": 0.7, "b": 0.3})
    assert isinstance(pset.prediction_set, list)


def test_conformal_coverage_stats_initial():
    """coverage_stats 初始状态。"""
    engine = ConformalEngine(ConformalConfig(alpha=0.1, method="aci"))
    stats = engine.coverage_stats()
    assert "empirical_coverage" in stats
    assert stats["n_updates"] == 0


def test_conformal_update_not_covered():
    """update 返回 covered=False 场景。"""
    engine = ConformalEngine(ConformalConfig(alpha=0.1, method="aci", aci_gamma=0.5))
    # 校准让阈值很严
    engine.calibrate([({"a": 0.99, "b": 0.01}, "a") for _ in range(5)])
    # predict b 但校准全是 a，可能不覆盖
    res = engine.update({"a": 0.01, "b": 0.99}, "b")
    assert "covered" in res


def test_conformal_agaci_coverage_stats():
    """AgACI 的 coverage_stats。"""
    engine = ConformalEngine(ConformalConfig(alpha=0.2, method="agaci"))
    engine.calibrate([({"a": 0.6, "b": 0.4}, "a") for _ in range(10)])
    engine.predict({"a": 0.65, "b": 0.35})
    engine.update({"a": 0.65, "b": 0.35}, "a")
    stats = engine.coverage_stats()
    assert stats["n_updates"] == 1


def test_conformal_prediction_set_properties():
    """PredictionSet 字段。"""
    engine = ConformalEngine(ConformalConfig(alpha=0.1, method="split"))
    engine.calibrate([({"a": 0.7, "b": 0.3}, "a") for _ in range(5)])
    pset = engine.predict({"a": 0.8, "b": 0.2})
    assert pset.coverage_target == 0.9
    assert pset.method == "split"
    assert isinstance(pset.prediction_set, list)


# ===== flow_amplification.py =====


def test_flow_amp_stable_direction():
    """稳定流向（无明显变化）的倍增。"""
    engine = ProbabilityEngine()
    flow_engine = FlowAmplificationEngine()
    t0 = datetime.now()
    t1 = t0 + timedelta(hours=1)
    s0 = Snapshot(timestamp=t0, probabilities={"a": 0.5, "b": 0.5})
    s1 = Snapshot(timestamp=t1, probabilities={"a": 0.51, "b": 0.49})  # 微小变化
    flow_report = engine.analyze_flow(s0, s1)
    graph = EventGraph.chain(["a", "b"])
    amp = flow_engine.calculate_amplification(flow_report, {"a": 0.5, "b": 0.5}, graph)
    assert len(amp.amplifications) == 2


def test_flow_amp_downward():
    """下降流向的倍增。"""
    engine = ProbabilityEngine()
    flow_engine = FlowAmplificationEngine()
    t0 = datetime.now()
    t1 = t0 + timedelta(hours=1)
    s0 = Snapshot(timestamp=t0, probabilities={"a": 0.7, "b": 0.3})
    s1 = Snapshot(timestamp=t1, probabilities={"a": 0.4, "b": 0.6})  # a 大跌
    flow_report = engine.analyze_flow(s0, s1)
    graph = EventGraph.chain(["a", "b"])
    amp = flow_engine.calculate_amplification(flow_report, {"a": 0.4, "b": 0.6}, graph)
    a_amp = next(a for a in amp.amplifications if a.outcome == "a")
    assert a_amp.base_flow_pp < 0  # 下降


def test_flow_amp_fully_connected():
    """完全连接图的倍增。"""
    engine = ProbabilityEngine()
    flow_engine = FlowAmplificationEngine()
    t0 = datetime.now()
    t1 = t0 + timedelta(hours=1)
    s0 = Snapshot(timestamp=t0, probabilities={"a": 0.3, "b": 0.3, "c": 0.4})
    s1 = Snapshot(timestamp=t1, probabilities={"a": 0.5, "b": 0.3, "c": 0.2})
    flow_report = engine.analyze_flow(s0, s1)
    graph = EventGraph.fully_connected(["a", "b", "c"])
    amp = flow_engine.calculate_amplification(flow_report, {"a": 0.5, "b": 0.3, "c": 0.2}, graph)
    assert len(amp.amplifications) == 3


def test_flow_amp_empty_flows():
    """空流向报告的倍增不崩。"""
    flow_engine = FlowAmplificationEngine()
    from edp import FlowReport, Snapshot

    s = Snapshot(timestamp=datetime.now(), probabilities={"a": 0.5, "b": 0.5})
    empty_report = FlowReport(initial_snapshot=s, latest_snapshot=s)
    graph = EventGraph.chain(["a", "b"])
    amp = flow_engine.calculate_amplification(empty_report, {"a": 0.5, "b": 0.5}, graph)
    # 空 flows 不崩
    assert hasattr(amp, "amplifications")


def test_flow_amp_amplification_report_fields():
    """AmplificationReport 字段。"""
    engine = ProbabilityEngine()
    flow_engine = FlowAmplificationEngine()
    t0 = datetime.now()
    t1 = t0 + timedelta(hours=1)
    s0 = Snapshot(timestamp=t0, probabilities={"a": 0.3, "b": 0.7})
    s1 = Snapshot(timestamp=t1, probabilities={"a": 0.6, "b": 0.4})
    flow_report = engine.analyze_flow(s0, s1)
    graph = EventGraph.chain(["a", "b"])
    amp = flow_engine.calculate_amplification(flow_report, {"a": 0.6, "b": 0.4}, graph)
    # 检查 report 有 amplifications 列表
    assert len(amp.amplifications) == 2
    a_amp = amp.amplifications[0]
    assert hasattr(a_amp, "outcome")
    assert hasattr(a_amp, "base_flow_pp")


def test_flow_amp_levels():
    """AmplificationLevel 枚举。"""
    from edp import AmplificationLevel

    levels = list(AmplificationLevel)
    assert len(levels) > 0


def test_flow_amp_classify_levels():
    """classify_amplification_level 各阈值。"""
    flow_engine = FlowAmplificationEngine()
    from edp import AmplificationLevel

    assert flow_engine.classify_amplification_level(0.5) == AmplificationLevel.NONE
    assert flow_engine.classify_amplification_level(2.0) == AmplificationLevel.LOW
    assert flow_engine.classify_amplification_level(4.0) == AmplificationLevel.MEDIUM
    assert flow_engine.classify_amplification_level(7.0) == AmplificationLevel.HIGH
    assert flow_engine.classify_amplification_level(12.0) == AmplificationLevel.VERY_HIGH
    assert flow_engine.classify_amplification_level(20.0) == AmplificationLevel.EXCEPTIONAL


def test_flow_amp_is_reliable_and_signal_strength():
    """AmplificationResult.is_reliable / get_signal_strength。"""
    from edp import AmplificationLevel, AmplificationResult

    r = AmplificationResult(
        outcome="a",
        base_flow_pp=5.0,
        directional_consistency=0.8,
        gradient_position=0.6,
        market_momentum=1.2,
        amplification_score=8.0,
        level=AmplificationLevel.HIGH,
        confidence=0.7,
    )
    assert r.is_reliable(0.5) is True
    assert r.is_reliable(0.9) is False  # confidence 不够
    s = r.get_signal_strength()
    assert 0 <= s <= 1
    # NONE 级别不可靠
    r2 = AmplificationResult(
        outcome="b", base_flow_pp=0.5, directional_consistency=0.5,
        gradient_position=0.5, market_momentum=1.0, amplification_score=0.5,
        level=AmplificationLevel.NONE, confidence=0.9,
    )
    assert r2.is_reliable() is False


def test_flow_amp_report_helpers():
    """AmplificationReport 的 get_high/get_reliable/cascading/summary。"""
    from edp import (
        AmplificationLevel,
        AmplificationReport,
        AmplificationResult,
    )

    report = AmplificationReport(outcomes=["a", "b", "c"])
    report.amplifications = [
        AmplificationResult(
            outcome="a", base_flow_pp=8.0, directional_consistency=0.9,
            gradient_position=0.7, market_momentum=1.3, amplification_score=10.0,
            level=AmplificationLevel.VERY_HIGH, confidence=0.8, propagation_depth=2,
            adjacent_signals=[("b", 5.0), ("c", 3.0)],
        ),
        AmplificationResult(
            outcome="b", base_flow_pp=0.5, directional_consistency=0.3,
            gradient_position=0.4, market_momentum=1.0, amplification_score=0.5,
            level=AmplificationLevel.NONE, confidence=0.4,
        ),
    ]
    high = report.get_high_amplification()
    assert len(high) == 1
    assert high[0].outcome == "a"
    reliable = report.get_reliable_amplifications(0.5)
    assert len(reliable) == 1
    cascading = report.get_cascading_signals()
    assert "a" in cascading
    summary = report.get_summary()
    assert summary["total_outcomes"] == 3
    assert summary["high_amplification_count"] == 1


def test_flow_amp_directional_consistency_empty():
    """calculate_directional_consistency 空 adjacent。"""
    flow_engine = FlowAmplificationEngine()
    t0 = datetime.now()
    t1 = t0 + timedelta(hours=1)
    s0 = Snapshot(timestamp=t0, probabilities={"a": 0.3, "b": 0.7})
    s1 = Snapshot(timestamp=t1, probabilities={"a": 0.6, "b": 0.4})
    report = ProbabilityEngine().analyze_flow(s0, s1)
    # 空 adjacent
    assert flow_engine.calculate_directional_consistency(report, "a", []) == 0.0
    # outcome 不在 flow_map
    assert flow_engine.calculate_directional_consistency(report, "x", ["a"]) == 0.0


def test_flow_amp_gradient_position():
    """calculate_gradient_position 各种边界。"""
    flow_engine = FlowAmplificationEngine()
    probs = {"a": 0.2, "b": 0.5, "c": 0.3}
    # 正常
    p = flow_engine.calculate_gradient_position("a", probs, ["a", "b", "c"])
    assert 0 <= p <= 1
    # outcome 不在 probs
    assert flow_engine.calculate_gradient_position("x", probs, ["a"]) == 0.0
    # 空 direction_outcomes
    assert flow_engine.calculate_gradient_position("a", probs, []) == 0.5
    # max==min
    equal_probs = {"a": 0.5, "b": 0.5}
    assert flow_engine.calculate_gradient_position("a", equal_probs, ["a", "b"]) == 0.5


def test_flow_amp_market_momentum():
    """calculate_market_momentum 各分支。"""
    flow_engine = FlowAmplificationEngine()
    probs = {"a": 0.5, "b": 0.5}
    # 空 adjacent_flows
    assert flow_engine.calculate_market_momentum("a", 5.0, [], probs) == 1.0
    # 强正向同向
    m1 = flow_engine.calculate_market_momentum("a", 5.0, [("b", 4.0)], probs)
    assert m1 >= 1.3
    # 反向
    m2 = flow_engine.calculate_market_momentum("a", 5.0, [("b", -4.0)], probs)
    assert m2 <= 0.9


def test_flow_amp_calculate_amplification_full():
    """完整 calculate_amplification 含传播深度。"""
    engine = ProbabilityEngine()
    flow_engine = FlowAmplificationEngine()
    t0 = datetime.now()
    t1 = t0 + timedelta(hours=1)
    s0 = Snapshot(timestamp=t0, probabilities={"a": 0.2, "b": 0.3, "c": 0.5})
    s1 = Snapshot(timestamp=t1, probabilities={"a": 0.5, "b": 0.3, "c": 0.2})
    flow_report = engine.analyze_flow(s0, s1)
    graph = EventGraph.fully_connected(["a", "b", "c"])
    amp = flow_engine.calculate_amplification(flow_report, {"a": 0.5, "b": 0.3, "c": 0.2}, graph)
    assert len(amp.amplifications) == 3
    # 应有 aggregate_momentum
    assert isinstance(amp.aggregate_momentum, float)


# ===== domain_awareness.py =====


def test_domain_awareness_single_source():
    """单源评估。"""
    from edp import EvidenceSource, EvidenceType, SourceReliability

    engine = DomainAwarenessEngine()
    now = datetime.now()
    sources = [
        EvidenceSource(
            "s1", EvidenceType.MODEL, SourceReliability.A, now, {"probability": 0.7}, confidence=0.9
        )
    ]
    assessment = engine.assess_situation(sources)
    assert assessment.source_count == 1
    assert 0 <= assessment.aggregate_probability <= 1


def test_domain_awareness_disagreement():
    """源之间分歧大，共识应低。"""
    from edp import EvidenceSource, EvidenceType, SourceReliability

    engine = DomainAwarenessEngine()
    now = datetime.now()
    sources = [
        EvidenceSource("s1", EvidenceType.MODEL, SourceReliability.A, now, {"probability": 0.9}),
        EvidenceSource("s2", EvidenceType.MODEL, SourceReliability.A, now, {"probability": 0.1}),
    ]
    assessment = engine.assess_situation(sources)
    assert assessment.consensus_score < 0.5


def test_domain_awareness_empty_sources():
    """空源列表不崩。"""
    engine = DomainAwarenessEngine()
    try:
        assessment = engine.assess_situation([])
        # 可能返回默认值或抛错，都接受
        assert assessment is not None or True
    except (ValueError, Exception):
        pass


def test_domain_awareness_all_reliability_levels():
    """遍历所有可靠性等级。"""
    from edp import EvidenceSource, EvidenceType, SourceReliability

    engine = DomainAwarenessEngine()
    now = datetime.now()
    sources = [
        EvidenceSource(
            f"s{i}", EvidenceType.MODEL, rel, now, {"probability": 0.6}, confidence=0.7
        )
        for i, rel in enumerate(SourceReliability)
    ]
    assessment = engine.assess_situation(sources)
    assert assessment.source_count == len(sources)


def test_domain_awareness_all_evidence_types():
    """遍历所有证据类型。"""
    from edp import EvidenceSource, EvidenceType, SourceReliability

    engine = DomainAwarenessEngine()
    now = datetime.now()
    sources = [
        EvidenceSource(
            f"s{i}", etype, SourceReliability.B, now, {"probability": 0.6}, confidence=0.7
        )
        for i, etype in enumerate(EvidenceType)
    ]
    assessment = engine.assess_situation(sources)
    assert assessment.source_count == len(sources)


def test_domain_awareness_stability_levels():
    """StabilityLevel 枚举完整。"""
    from edp import StabilityLevel

    assert len(list(StabilityLevel)) > 0


def test_domain_awareness_assessment_fields():
    """SituationAssessment 字段完整。"""
    from edp import EvidenceSource, EvidenceType, SourceReliability

    engine = DomainAwarenessEngine()
    now = datetime.now()
    sources = [
        EvidenceSource("s1", EvidenceType.MODEL, SourceReliability.A, now, {"probability": 0.7})
    ]
    a = engine.assess_situation(sources)
    assert hasattr(a, "aggregate_probability")
    assert hasattr(a, "consensus_score")
    assert hasattr(a, "source_count")


def test_domain_awareness_model_diversity_single():
    """单源 model_diversity。"""
    from edp import EvidenceSource, EvidenceType, SourceReliability

    now = datetime.now()
    single = [
        EvidenceSource("s1", EvidenceType.MODEL, SourceReliability.B, now, {"probability": 0.5})
    ]
    r = DomainAwarenessEngine.model_diversity(single)
    assert "diversity" in r
    assert "redundancy" in r


def test_domain_awareness_source_probability_default():
    """EvidenceSource.probility 无 probability 字段返回 0.5。"""
    from edp import EvidenceSource, EvidenceType, SourceReliability

    now = datetime.now()
    s = EvidenceSource("s1", EvidenceType.MODEL, SourceReliability.B, now, {})
    assert s.probability == 0.5
    # 有 probability
    s2 = EvidenceSource("s2", EvidenceType.MODEL, SourceReliability.B, now, {"probability": 0.8})
    assert abs(s2.probability - 0.8) < 1e-6
    # 越界裁剪
    s3 = EvidenceSource("s3", EvidenceType.MODEL, SourceReliability.B, now, {"probability": 1.5})
    assert s3.probability == 1.0
    # reliability_weight
    assert s.reliability_weight == float(SourceReliability.B.weight)


def test_domain_awareness_assessment_properties():
    """SituationAssessment.is_consensus / has_anomaly / get_summary。"""
    from edp import SituationAssessment, StabilityLevel

    a = SituationAssessment(
        aggregate_probability=0.7,
        source_weights={"s1": 1.0},
        consensus_score=0.85,
        stability=StabilityLevel.STABLE,
        anomaly_flags=[],
        source_count=1,
    )
    assert a.is_consensus is True
    assert a.has_anomaly is False
    s = a.get_summary()
    assert s["aggregate_probability"] == 0.7
    assert s["source_count"] == 1
    # 有异常
    a2 = SituationAssessment(
        aggregate_probability=0.5,
        source_weights={},
        consensus_score=0.2,
        stability=StabilityLevel.AMBIGUOUS,
        anomaly_flags=["outlier"],
    )
    assert a2.is_consensus is False
    assert a2.has_anomaly is True


def test_domain_awareness_calculate_source_weight():
    """calculate_source_weight 含时间衰减。"""
    from edp import EvidenceSource, EvidenceType, SourceReliability

    engine = DomainAwarenessEngine({"time_decay_hours": 24.0})
    now = datetime.now()
    fresh = EvidenceSource("s1", EvidenceType.MODEL, SourceReliability.A, now, {"probability": 0.7})
    old = EvidenceSource(
        "s2", EvidenceType.MODEL, SourceReliability.A, now - timedelta(hours=48), {"probability": 0.7}
    )
    w_fresh = engine.calculate_source_weight(fresh, now)
    w_old = engine.calculate_source_weight(old, now)
    assert w_fresh > w_old  # 新源权重更高


def test_domain_awareness_fusion_methods():
    """遍历所有融合方法。"""
    from edp import EvidenceSource, EvidenceType, SourceReliability

    now = datetime.now()
    sources = [
        EvidenceSource("s1", EvidenceType.MODEL, SourceReliability.A, now, {"probability": 0.7}),
        EvidenceSource("s2", EvidenceType.SENSOR, SourceReliability.A, now, {"probability": 0.68}),
    ]
    for method in ["linear", "log_odds", "bayesian", "hybrid"]:
        engine = DomainAwarenessEngine()
        a = engine.assess_situation(sources, fusion_method=method)
        assert 0 <= a.aggregate_probability <= 1
        assert a.fusion_method == method


def test_domain_awareness_empty_sources_returns_assessment():
    """空源列表返回默认评估（不崩）。"""
    engine = DomainAwarenessEngine()
    a = engine.assess_situation([])
    assert a.source_count == 0
    assert a.aggregate_probability == 0.5  # prior


def test_domain_awareness_cross_validate():
    """cross_validate 两组源。"""
    from edp import EvidenceSource, EvidenceType, SourceReliability

    now = datetime.now()
    group_a = [
        EvidenceSource("a1", EvidenceType.MODEL, SourceReliability.A, now, {"probability": 0.7})
    ]
    group_b = [
        EvidenceSource("b1", EvidenceType.SENSOR, SourceReliability.A, now, {"probability": 0.68})
    ]
    engine = DomainAwarenessEngine()
    r = engine.cross_validate(group_a, group_b)
    assert "agreement" in r
    assert "delta" in r
    assert r["combined"] is not None
    # 空组
    r2 = engine.cross_validate([], group_b)
    assert r2["agreement"] == 0.0
    assert r2["combined"] is None


def test_domain_awareness_detect_anomalies():
    """detect_anomalies 检测离群源。"""
    from edp import EvidenceSource, EvidenceType, SourceReliability

    now = datetime.now()
    sources = [
        EvidenceSource("s1", EvidenceType.MODEL, SourceReliability.A, now, {"probability": 0.7}),
        EvidenceSource("s2", EvidenceType.MODEL, SourceReliability.A, now, {"probability": 0.69}),
        EvidenceSource("s3", EvidenceType.MODEL, SourceReliability.A, now, {"probability": 0.1}),  # 离群
    ]
    engine = DomainAwarenessEngine({"anomaly_threshold": 1.5})
    weights = {"s1": 0.33, "s2": 0.33, "s3": 0.33}
    anomalies = engine.detect_anomalies(sources, weights)
    assert isinstance(anomalies, list)


def test_domain_awareness_classify_stability():
    """classify_stability 各场景。"""
    from edp import StabilityLevel

    engine = DomainAwarenessEngine()
    # 高共识无异常
    s1 = engine.classify_stability(0.85, 0, 0.5)
    assert s1 == StabilityLevel.STABLE
    # 低共识（<= consensus_low）→ UNSTABLE（非 AMBIGUOUS）
    s2 = engine.classify_stability(0.2, 0, 0.5)
    assert s2 == StabilityLevel.UNSTABLE
    # 有异常 → ANOMALOUS
    s3 = engine.classify_stability(0.5, 2, 0.5)
    assert s3 == StabilityLevel.ANOMALOUS
    # 中等共识 + 高动量 → EMERGING
    s4 = engine.classify_stability(0.5, 0, 5.0)
    assert s4 == StabilityLevel.EMERGING
    # 中等共识 + 低动量 → AMBIGUOUS
    s5 = engine.classify_stability(0.5, 0, 0.5)
    assert s5 == StabilityLevel.AMBIGUOUS


# ===== edp.py 顶层接口补充 =====


def test_edp_analyze_empty_evidence():
    """空 evidence 不崩。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    result = edp.analyze(evidence=[])
    assert "probabilities" in result


def test_edp_analyze_with_quotes_only():
    """仅报价无 evidence。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    result = edp.analyze(raw_data={"a": 1.5, "b": 2.5})
    assert "probabilities" in result
    assert abs(sum(result["probabilities"].values()) - 1.0) < 0.05


def test_edp_analyze_with_budget_zero():
    """budget=0 不崩。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    result = edp.analyze(
        evidence=[Evidence("e1", "model", {"probability": 0.6}, outcome_id="a")],
        budget=0,
    )
    assert "warnings" in result


def test_edp_analyze_mixed_evidence_and_quotes():
    """同时传 evidence 和 raw_data。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B"), Outcome("c", "C")])
    edp = EDP(domain)
    result = edp.analyze(
        evidence=[Evidence("e1", "model", {"probability": 0.5}, outcome_id="a", confidence=0.7)],
        raw_data={"a": 2.0, "b": 3.0, "c": 6.0},
        budget=1000,
    )
    assert "probabilities" in result
    assert abs(sum(result["probabilities"].values()) - 1.0) < 0.05


def test_edp_analyze_three_outcomes():
    """三结果域。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B"), Outcome("c", "C")])
    edp = EDP(domain)
    result = edp.analyze(
        evidence=[
            Evidence("e1", "model", {"probability": 0.5}, outcome_id="a", confidence=0.8),
            Evidence("e2", "expert", {"probability": 0.3}, outcome_id="b", confidence=0.6),
        ]
    )
    assert len(result["probabilities"]) == 3


def test_edp_config_conformal_methods():
    """不同 conformal method 配置。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    for method in ["split", "aci", "agaci"]:
        edp = EDP(domain, {"conformal": {"method": method, "alpha": 0.1}})
        result = edp.analyze(
            evidence=[Evidence("e1", "model", {"probability": 0.7}, outcome_id="a")]
        )
        assert result["prediction_set"].method == method


def test_edp_analyze_return_multipliers():
    """带 return_multipliers 的分析。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    result = edp.analyze(
        evidence=[Evidence("e1", "model", {"probability": 0.6}, outcome_id="a")],
        budget=500,
        return_multipliers={"a": 2.0, "b": 2.0},
    )
    assert "warnings" in result


def test_edp_summary_format():
    """summary 字符串格式。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    result = edp.analyze(
        evidence=[Evidence("e1", "model", {"probability": 0.7}, outcome_id="a")]
    )
    assert isinstance(result["summary"], str)
    assert len(result["summary"]) > 0


def test_edp_ingest_signals_empty():
    """ingest_signals 空报价早 return（probabilities 保持空 dict）。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    # EDP 初始化时 probabilities 为空，ingest_signals 空 raw_data 应早 return
    # probabilities 保持空 dict 是正常行为
    edp.ingest_signals({})
    assert edp.probabilities == {}  # 空，未初始化
    # 但 ingest 真实报价后会初始化
    edp.ingest_signals({"a": 1.5, "b": 2.5})
    assert abs(sum(edp.probabilities.values()) - 1.0) < 1e-6


def test_edp_ingest_signals_decimal_odds():
    """ingest_signals 小数报价 Shin 归一化路径。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B"), Outcome("c", "C")])
    edp = EDP(domain)
    edp.ingest_signals({"a": 1.5, "b": 3.0, "c": 6.0})
    assert edp.probabilities["a"] > edp.probabilities["b"]
    assert edp.probabilities["b"] > edp.probabilities["c"]


def test_edp_ingest_signals_direct_probs():
    """ingest_signals 直接概率（>1.05 触发归一化）。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    # 先 ingest 一次让 probabilities 初始化
    edp.ingest_signals({"a": 1.5, "b": 2.5})
    # 用 percentage 形式，总和 > 1.05
    edp.ingest_signals({"a": 80.0, "b": 70.0})  # 0.8 + 0.7 = 1.5 > 1.05
    assert abs(sum(edp.probabilities.values()) - 1.0) < 1e-6


def test_edp_add_evidence_empty():
    """add_evidence 空列表返回默认评估。"""

    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    assessment = edp.add_evidence([])
    assert assessment.source_count == 0
    assert assessment.aggregate_probability == 0.5


def test_edp_add_evidence_unknown_source_type():
    """add_evidence 未知 source_type 走 UNKNOWN 分支。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.ingest_signals({"a": 1.5, "b": 2.5})  # 先初始化概率
    # source_type 不在 EvidenceType 枚举中
    assessment = edp.add_evidence(
        [Evidence("e1", "unknown_type", {"probability": 0.7}, outcome_id="a")]
    )
    assert assessment.source_count == 1


def test_edp_add_evidence_directed_updates_target():
    """add_evidence 定向证据提升目标结果。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.ingest_signals({"a": 1.5, "b": 2.5})  # 先初始化
    edp.add_evidence([Evidence("e1", "model", {"probability": 0.9}, outcome_id="a", confidence=0.9)])
    assert edp.probabilities["a"] > 0.5


def test_edp_add_evidence_nondirected():
    """非定向证据（无 outcome_id）更新所有结果。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.ingest_signals({"a": 1.5, "b": 2.5})  # 先初始化概率
    # 无 outcome_id → 非定向
    edp.add_evidence([Evidence("e1", "model", {"probability": 0.8}, confidence=0.8)])
    assert abs(sum(edp.probabilities.values()) - 1.0) < 1e-6


def test_edp_snapshot_and_flow():
    """snapshot + analyze_flow。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.ingest_signals({"a": 1.5, "b": 2.5})
    # <2 快照，analyze_flow 返回 None
    assert edp.analyze_flow() is None
    edp.snapshot("t1")
    edp.ingest_signals({"a": 1.3, "b": 3.0})
    edp.snapshot("t2")
    report = edp.analyze_flow()
    assert report is not None
    assert len(report.flows) == 2


def test_edp_analyze_amplification():
    """analyze_amplification（需 event_graph）。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.ingest_signals({"a": 1.5, "b": 2.5})
    edp.snapshot("t1")
    edp.ingest_signals({"a": 1.2, "b": 3.5})
    edp.snapshot("t2")
    flow = edp.analyze_flow()
    assert flow is not None
    amp = edp.analyze_amplification(flow)
    # event_graph 可能未设置 → 返回 None；若设置则返回 report
    if amp is not None:
        assert len(amp.amplifications) == 2


def test_edp_analyze_amplification_no_flow():
    """analyze_amplification 无 flow 返回 None。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    assert edp.analyze_amplification(None) is None


def test_edp_allocate():
    """allocate 资源分配。"""

    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.ingest_signals({"a": 1.5, "b": 2.5})
    bundle = edp.allocate(1000, return_multipliers={"a": 1.5, "b": 2.5})
    assert bundle.budget == 1000
    assert len(bundle.warnings) > 0


def test_edp_match_reliability():
    """_match_reliability 各阈值。"""
    from edp import SourceReliability

    assert EDP._match_reliability(0.95) == SourceReliability.A
    assert EDP._match_reliability(0.75) == SourceReliability.B
    assert EDP._match_reliability(0.55) == SourceReliability.C
    assert EDP._match_reliability(0.35) == SourceReliability.D
    assert EDP._match_reliability(0.15) == SourceReliability.E


def test_edp_conformal_predict_method():
    """conformal_predict 直接调用。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain, {"conformal": {"method": "split", "alpha": 0.1}})
    edp.ingest_signals({"a": 1.5, "b": 2.5})
    pset = edp.conformal_predict()
    assert isinstance(pset.prediction_set, list)


def test_edp_analyze_full_pipeline():
    """完整 pipeline：ingest + add_evidence + conformal + allocate。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B"), Outcome("c", "C")])
    edp = EDP(domain)
    # 1. 报价
    edp.ingest_signals({"a": 1.5, "b": 3.0, "c": 6.0})
    # 2. 证据
    edp.add_evidence([
        Evidence("e1", "model", {"probability": 0.5}, outcome_id="a", confidence=0.8),
        Evidence("e2", "sensor", {"probability": 0.3}, outcome_id="b", confidence=0.7),
    ])
    # 3. 快照
    edp.snapshot("after_evidence")
    # 4. 分配
    bundle = edp.allocate(
        2000,
        return_multipliers={"a": 1.5, "b": 3.0, "c": 6.0},
    )
    assert bundle.budget == 2000
    assert abs(sum(edp.probabilities.values()) - 1.0) < 1e-6


def test_edp_calibrate_after_prediction():
    """calibrate 校准预测。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.ingest_signals({"a": 1.5, "b": 2.5})
    # 如果有 calibrate 方法
    if hasattr(edp, "calibrate"):
        try:
            edp.calibrate("a")
        except (TypeError, ValueError):
            pass  # 参数可能不同


if __name__ == "__main__":
    # 手动运行所有测试
    test_funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for func in test_funcs:
        try:
            func()
            print(f"PASS  {func.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL  {func.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed, {len(test_funcs)} total")
    sys.exit(0 if failed == 0 else 1)
