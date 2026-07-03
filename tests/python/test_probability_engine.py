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
    submodule_search_locations=[
        os.path.join(os.path.dirname(__file__), "..", "..", "src", "python")
    ],
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
    amp_report = flow_engine.calculate_amplification(flow_report, {"a": 0.5, "b": 0.5}, graph)
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
        EvidenceSource(
            "s1", EvidenceType.MODEL, SourceReliability.B, now, {"probability": 0.7}, confidence=0.8
        ),
        EvidenceSource(
            "s2",
            EvidenceType.SENSOR,
            SourceReliability.A,
            now,
            {"probability": 0.68},
            confidence=0.9,
        ),
        EvidenceSource(
            "s3",
            EvidenceType.MODEL,
            SourceReliability.C,
            now,
            {"probability": 0.65},
            confidence=0.5,
        ),
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
        outcome_id="a",
        probability=0.6,
        return_multiplier=2.0,
        flow_direction="upward",
        confidence=0.8,
    )
    ok, _ = engine.validate_three_principles(leg)
    assert ok is True
    # 不满足：负期望
    leg = AllocationLeg(
        outcome_id="a",
        probability=0.3,
        return_multiplier=1.5,
        flow_direction="upward",
        confidence=0.8,
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
# 补充测试：calibration.py 覆盖率提升
# ----------------------------------------------------------------------


def test_calibration_record_empty_predictions():
    """空预测字典时 predicted_top_outcome 应返回空串。"""
    from edp.calibration import PredictionRecord

    rec = PredictionRecord(timestamp="t", predicted_probabilities={}, actual_outcome="a")
    assert rec.predicted_top_outcome == ""
    assert rec.is_top1_correct is False
    assert rec.predicted_actual_probability == 0.0


def test_calibration_record_predicted_actual_probability():
    """predicted_actual_probability 属性应返回实际结果的预测概率。"""
    from edp.calibration import PredictionRecord

    rec = PredictionRecord(
        timestamp="t",
        predicted_probabilities={"a": 0.6, "b": 0.4},
        actual_outcome="b",
    )
    assert abs(rec.predicted_actual_probability - 0.4) < 1e-9
    assert rec.predicted_top_outcome == "a"
    assert rec.is_top1_correct is False


def test_calibration_compute_brier_empty():
    """空预测字典时 Brier 分数应为 0。"""
    assert CalibrationEngine._compute_brier({}, "a") == 0.0


def test_calibration_hyvarinen_empty():
    """空预测字典时 Hyvärinen 分数应为 0。"""
    calib = CalibrationEngine()
    assert calib.hyvarinen_score({}, "a") == 0.0


def test_calibration_brier_decomposition_default_empty():
    """无内部历史时 brier_decomposition 默认提取空历史返回全 0。"""
    calib = CalibrationEngine()
    decomp = calib.brier_decomposition()
    assert decomp["brier_score"] == 0.0
    assert decomp["reliability"] == 0.0
    assert decomp["uncertainty"] == 0.0
    assert decomp["net_score"] == 0.0


def test_calibration_brier_decomposition_from_internal_history():
    """brier_decomposition 不传 history 时应从内部历史提取二分类序列。"""
    calib = CalibrationEngine()
    calib.evaluate({"a": 0.8, "b": 0.2}, "a")
    calib.evaluate({"a": 0.3, "b": 0.7}, "b")
    calib.evaluate({"a": 0.6, "b": 0.4}, "a")
    decomp = calib.brier_decomposition()
    assert decomp["brier_score"] >= 0.0
    assert "resolution" in decomp
    assert "uncertainty" in decomp


def test_calibration_curve_default_empty():
    """无内部历史时 calibration_curve 默认返回空列表。"""
    calib = CalibrationEngine()
    assert calib.calibration_curve() == []


def test_calibration_curve_from_internal_history():
    """calibration_curve 不传 history 时应从内部历史提取。"""
    calib = CalibrationEngine()
    calib.evaluate({"a": 0.8, "b": 0.2}, "a")
    calib.evaluate({"a": 0.6, "b": 0.4}, "a")
    curve = calib.calibration_curve()
    assert len(curve) > 0
    for pred, obs, count in curve:
        assert count > 0


def test_calibration_crps_basic():
    """CRPS 应对 CDF 采样点积分（覆盖指示函数两个分支）。"""
    calib = CalibrationEngine()
    cdf = [(0.0, 0.0), (2.0, 0.5), (4.0, 1.0), (6.0, 1.0)]
    val = calib.crps(cdf, actual_value=3.0)
    assert val >= 0.0


def test_calibration_crps_empty():
    """空 CDF 时 CRPS 应为 0。"""
    calib = CalibrationEngine()
    assert calib.crps([], actual_value=1.0) == 0.0


def test_calibration_crps_duplicate_x():
    """重复 x 值（dx<=0）应被跳过不报错。"""
    calib = CalibrationEngine()
    cdf = [(1.0, 0.3), (1.0, 0.4), (2.0, 0.9)]
    val = calib.crps(cdf, actual_value=1.5)
    assert val >= 0.0


def test_calibration_long_term_performance_empty():
    """无历史时 long_term_performance 应返回零统计。"""
    calib = CalibrationEngine()
    perf = calib.long_term_performance()
    assert perf["total_predictions"] == 0
    assert perf["top1_accuracy"] == 0.0
    assert perf["avg_brier"] == 0.0


def test_calibration_long_term_performance_with_history():
    """有历史时 long_term_performance 应返回统计与 Brier 分解。"""
    calib = CalibrationEngine()
    calib.evaluate({"a": 0.7, "b": 0.3}, "a")
    calib.evaluate({"a": 0.4, "b": 0.6}, "b")
    perf = calib.long_term_performance()
    assert perf["total_predictions"] == 2
    assert 0.0 <= perf["top1_accuracy"] <= 1.0
    assert "brier_decomposition" in perf
    assert "avg_actual_probability" in perf


def test_calibration_reset():
    """reset 应清空历史。"""
    calib = CalibrationEngine()
    calib.evaluate({"a": 0.7, "b": 0.3}, "a")
    assert len(calib.history) == 1
    calib.reset()
    assert len(calib.history) == 0


# ----------------------------------------------------------------------
# 补充测试：conformal.py 覆盖率提升
# ----------------------------------------------------------------------


def test_conformal_prediction_set_size_property():
    """PredictionSet.size 属性应返回预测集大小。"""
    engine = ConformalEngine(ConformalConfig(alpha=0.1, method="split"))
    engine.calibrate([({"a": 0.7, "b": 0.3}, "a") for _ in range(5)])
    pset = engine.predict({"a": 0.75, "b": 0.25})
    assert pset.size == len(pset.prediction_set)


def test_conformal_invalid_alpha_raises():
    """alpha 不在 (0,1) 应抛 ValueError。"""
    import pytest

    with pytest.raises(ValueError):
        ConformalEngine(ConformalConfig(alpha=0.0))
    with pytest.raises(ValueError):
        ConformalEngine(ConformalConfig(alpha=1.0))


def test_conformal_add_calibration_point_window_trim():
    """window_size 应触发校准分数滑动窗口裁剪。"""
    engine = ConformalEngine(ConformalConfig(alpha=0.1, method="split", window_size=3))
    for _ in range(10):
        engine.add_calibration_point({"a": 0.5, "b": 0.5}, "a")
    assert len(engine.calibration_scores) == 3


def test_conformal_unknown_method_raises():
    """未知 method 应抛 ValueError。"""
    import pytest

    engine = ConformalEngine(ConformalConfig(alpha=0.1, method="split"))
    engine.method = "bogus"
    with pytest.raises(ValueError):
        engine.predict({"a": 0.7, "b": 0.3})


def test_conformal_agaci_update_path():
    """AgACI 在线更新应触发子 ACI 更新与权重 softmax。"""
    engine = ConformalEngine(ConformalConfig(alpha=0.2, method="agaci"))
    engine.calibrate([({"a": 0.6, "b": 0.4}, "a") for _ in range(8)])
    res = engine.update({"a": 0.65, "b": 0.35}, "a")
    assert "covered" in res
    # 多次更新以触发权重 softmax 完整路径
    for _ in range(3):
        engine.update({"a": 0.4, "b": 0.6}, "b")
    stats = engine.coverage_stats()
    assert stats["method"] == "agaci"
    assert stats["n_updates"] == 4


def test_conformal_coverage_stats_no_errors():
    """无更新时 coverage_stats 应返回 None 经验覆盖率。"""
    engine = ConformalEngine(ConformalConfig(alpha=0.1, method="split"))
    stats = engine.coverage_stats()
    assert stats["n_updates"] == 0
    assert stats["empirical_coverage"] is None


# ----------------------------------------------------------------------
# 补充测试：flow_amplification.py 覆盖率提升
# ----------------------------------------------------------------------


def _make_flow_result(outcome, flow_pp, direction):
    from edp.probability_engine import FlowResult

    return FlowResult(
        outcome=outcome,
        flow_pp=flow_pp,
        direction=direction,
        initial_prob=0.5,
        latest_prob=0.5 + flow_pp / 100.0,
        momentum_score=abs(flow_pp),
    )


def _make_flow_report(flows):
    from edp.probability_engine import FlowReport

    return FlowReport(initial_snapshot=None, latest_snapshot=None, flows=flows)


def test_amp_result_is_reliable():
    """is_reliable 应同时考虑 confidence 与 level。"""
    from edp.flow_amplification import AmplificationLevel, AmplificationResult

    reliable = AmplificationResult(
        outcome="a", base_flow_pp=5, directional_consistency=0.8,
        gradient_position=0.5, market_momentum=1.2,
        amplification_score=7.0, level=AmplificationLevel.HIGH, confidence=0.8,
    )
    assert reliable.is_reliable(0.5) is True
    none_level = AmplificationResult(
        outcome="b", base_flow_pp=0, directional_consistency=0.0,
        gradient_position=0.0, market_momentum=1.0,
        amplification_score=0.0, level=AmplificationLevel.NONE, confidence=0.9,
    )
    assert none_level.is_reliable(0.5) is False
    low_conf = AmplificationResult(
        outcome="c", base_flow_pp=5, directional_consistency=0.8,
        gradient_position=0.5, market_momentum=1.2,
        amplification_score=7.0, level=AmplificationLevel.HIGH, confidence=0.2,
    )
    assert low_conf.is_reliable(0.5) is False


def test_amp_result_signal_strength():
    """get_signal_strength 应归一化到 [0,1]。"""
    from edp.flow_amplification import AmplificationLevel, AmplificationResult

    big = AmplificationResult(
        outcome="a", base_flow_pp=20, directional_consistency=0.8,
        gradient_position=0.5, market_momentum=1.2,
        amplification_score=25.0, level=AmplificationLevel.EXCEPTIONAL, confidence=1.0,
    )
    assert big.get_signal_strength() == 1.0
    small = AmplificationResult(
        outcome="b", base_flow_pp=2, directional_consistency=0.5,
        gradient_position=0.3, market_momentum=1.0,
        amplification_score=2.0, level=AmplificationLevel.LOW, confidence=1.0,
    )
    assert abs(small.get_signal_strength() - 0.2) < 1e-9


def test_amp_report_match_id_and_summary():
    """match_id 与 get_summary 应正常返回。"""
    from edp.flow_amplification import (
        AmplificationLevel, AmplificationReport, AmplificationResult,
    )

    amp = AmplificationResult(
        outcome="a", base_flow_pp=5, directional_consistency=0.8,
        gradient_position=0.5, market_momentum=1.3,
        amplification_score=7.0, level=AmplificationLevel.HIGH, confidence=0.9,
        propagation_depth=2, adjacent_signals=[("b", 5.0), ("c", 3.0)],
    )
    report = AmplificationReport(
        outcomes=["a", "b"], amplifications=[amp],
        aggregate_momentum=7.0, market_cascade_risk=0.2,
    )
    assert report.match_id.startswith("amp_")
    summary = report.get_summary()
    assert summary["total_outcomes"] == 2
    assert summary["high_amplification_count"] == 1
    assert summary["reliable_signals"] == 1
    assert len(summary["top_signals"]) == 1


def test_amp_report_high_reliable_cascading():
    """get_high_amplification / get_reliable_amplifications / get_cascading_signals。"""
    from edp.flow_amplification import (
        AmplificationLevel, AmplificationReport, AmplificationResult,
    )

    high = AmplificationResult(
        outcome="a", base_flow_pp=8, directional_consistency=0.9,
        gradient_position=0.4, market_momentum=1.3,
        amplification_score=8.0, level=AmplificationLevel.HIGH, confidence=0.8,
        propagation_depth=2, adjacent_signals=[("b", 5.0), ("c", 3.0), ("d", 1.0)],
    )
    low = AmplificationResult(
        outcome="x", base_flow_pp=2, directional_consistency=0.5,
        gradient_position=0.3, market_momentum=1.0,
        amplification_score=2.0, level=AmplificationLevel.LOW, confidence=0.6,
    )
    report = AmplificationReport(outcomes=["a", "x"], amplifications=[high, low])
    high_list = report.get_high_amplification()
    assert len(high_list) == 1
    assert high_list[0].outcome == "a"
    reliable = report.get_reliable_amplifications(0.5)
    assert any(r.outcome == "a" for r in reliable)
    cascade = report.get_cascading_signals()
    assert "a" in cascade
    assert cascade["a"] == ["b", "c"]


def test_amp_classify_all_levels():
    """classify_amplification_level 应覆盖所有等级。"""
    from edp.flow_amplification import AmplificationLevel

    engine = FlowAmplificationEngine()
    assert engine.classify_amplification_level(0.5) == AmplificationLevel.NONE
    assert engine.classify_amplification_level(2.0) == AmplificationLevel.LOW
    assert engine.classify_amplification_level(4.0) == AmplificationLevel.MEDIUM
    assert engine.classify_amplification_level(8.0) == AmplificationLevel.HIGH
    assert engine.classify_amplification_level(12.0) == AmplificationLevel.VERY_HIGH
    assert engine.classify_amplification_level(20.0) == AmplificationLevel.EXCEPTIONAL
    # 负分按绝对值分类
    assert engine.classify_amplification_level(-2.0) == AmplificationLevel.LOW


def test_amp_directional_consistency_branches():
    """calculate_directional_consistency 各分支。"""
    engine = FlowAmplificationEngine()
    # 无相邻
    assert engine.calculate_directional_consistency(_make_flow_report([]), "a", []) == 0.0
    # 目标结果不在 flow_map
    fr = _make_flow_report([_make_flow_result("b", 5.0, FlowDirection.UPWARD)])
    assert engine.calculate_directional_consistency(fr, "a", ["b"]) == 0.0
    # UPWARD 主向 + UPWARD 相邻（全一致）
    fa = _make_flow_result("a", 5.0, FlowDirection.UPWARD)
    fb = _make_flow_result("b", 3.0, FlowDirection.UPWARD)
    fr = _make_flow_report([fa, fb])
    assert abs(engine.calculate_directional_consistency(fr, "a", ["b"]) - 1.0) < 1e-9
    # UPWARD 主向 + STABLE 相邻（半一致）
    fs = _make_flow_result("s", 0.0, FlowDirection.STABLE)
    fr = _make_flow_report([fa, fs])
    assert abs(engine.calculate_directional_consistency(fr, "a", ["s"]) - 0.5) < 1e-9
    # STABLE 主向 + STABLE 相邻
    fs2 = _make_flow_result("s2", 0.0, FlowDirection.STABLE)
    fr = _make_flow_report([fs, fs2])
    assert abs(engine.calculate_directional_consistency(fr, "s", ["s2"]) - 0.5) < 1e-9
    # 相邻不在 flow_map → continue
    fr = _make_flow_report([fa])
    assert engine.calculate_directional_consistency(fr, "a", ["ghost"]) == 0.0


def test_amp_gradient_position_branches():
    """calculate_gradient_position 各分支。"""
    engine = FlowAmplificationEngine()
    # 目标不在概率字典
    assert engine.calculate_gradient_position("z", {"a": 0.5, "b": 0.5}, ["a", "b"]) == 0.0
    # direction_outcomes 为空
    assert engine.calculate_gradient_position("a", {"a": 0.5}, []) == 0.5
    # max == min
    assert engine.calculate_gradient_position("a", {"a": 0.5, "b": 0.5}, ["a", "b"]) == 0.5
    # 正常计算：a=0.2(最低) → position=1.0
    assert abs(engine.calculate_gradient_position("a", {"a": 0.2, "b": 0.8}, ["a", "b"]) - 1.0) < 1e-9
    # b 为最高 → position=0.0
    assert abs(engine.calculate_gradient_position("b", {"a": 0.2, "b": 0.8}, ["a", "b"]) - 0.0) < 1e-9


def test_amp_market_momentum_branches():
    """calculate_market_momentum 各动量区间。"""
    engine = FlowAmplificationEngine()
    probs = {"b": 0.5}
    # 无相邻 → 1.0
    assert engine.calculate_market_momentum("a", 1.0, [], probs) == 1.0
    # base_flow>=0, adj 同向（avg=|adj_flow|）
    assert engine.calculate_market_momentum("a", 1.0, [("b", 5.0)], probs) == 1.5
    assert engine.calculate_market_momentum("a", 1.0, [("b", 2.0)], probs) == 1.3
    assert engine.calculate_market_momentum("a", 1.0, [("b", 0.5)], probs) == 1.1
    # base_flow>=0, adj 反向（avg=-|adj_flow|）
    assert engine.calculate_market_momentum("a", 1.0, [("b", -0.5)], probs) == 0.9
    assert engine.calculate_market_momentum("a", 1.0, [("b", -2.0)], probs) == 0.8
    assert engine.calculate_market_momentum("a", 1.0, [("b", -5.0)], probs) == 0.7


def test_amp_propagation_depth_adj_without_flow():
    """calculate_propagation_depth 相邻节点无对应 flow 时应跳过。"""
    engine = FlowAmplificationEngine()
    fa = _make_flow_result("a", 10.0, FlowDirection.UPWARD)
    fb = _make_flow_result("b", 8.0, FlowDirection.UPWARD)
    fr = _make_flow_report([fa, fb])
    graph = EventGraph.chain(["a", "b", "c"])  # c 无对应 flow
    depth, signals = engine.calculate_propagation_depth("a", 10.0, graph, fr)
    assert depth >= 1
    assert any(s == "b" for s, _ in signals)


def test_amp_calculate_amplification_no_event_graph():
    """未提供 EventGraph 时应自动构建空图（无传播）。"""
    engine = FlowAmplificationEngine()
    fa = _make_flow_result("a", 10.0, FlowDirection.UPWARD)
    fb = _make_flow_result("b", -3.0, FlowDirection.DOWNWARD)
    fr = _make_flow_report([fa, fb])
    report = engine.calculate_amplification(fr, {"a": 0.6, "b": 0.4}, event_graph=None)
    assert len(report.amplifications) == 2
    a_amp = next(a for a in report.amplifications if a.outcome == "a")
    assert a_amp.amplification_score > 0


# ----------------------------------------------------------------------
# 补充测试：domain_awareness.py 覆盖率提升
# ----------------------------------------------------------------------


def _make_source(sid, prob, confidence=0.8, reliability=None, has_prob=True):
    from edp import EvidenceSource, EvidenceType, SourceReliability

    data = {"probability": prob} if has_prob else {}
    return EvidenceSource(
        source_id=sid,
        evidence_type=EvidenceType.MODEL,
        reliability=reliability or SourceReliability.B,
        timestamp=datetime.now(),
        data=data,
        confidence=confidence,
    )


def test_evidence_source_probability_default():
    """data 无 probability 时 probability 属性应返回 0.5。"""
    from edp import EvidenceSource, EvidenceType, SourceReliability

    s = EvidenceSource(
        source_id="s", evidence_type=EvidenceType.MODEL,
        reliability=SourceReliability.B, timestamp=datetime.now(),
        data={}, confidence=0.8,
    )
    assert s.probability == 0.5


def test_situation_assessment_properties_and_summary():
    """is_consensus / has_anomaly / get_summary。"""
    from edp import SituationAssessment, StabilityLevel

    sa = SituationAssessment(
        aggregate_probability=0.7, source_weights={"s": 1.0},
        consensus_score=0.85, stability=StabilityLevel.STABLE,
        anomaly_flags=[], source_count=2, fusion_method="hybrid", confidence=0.8,
    )
    assert sa.is_consensus is True
    assert sa.has_anomaly is False
    sa2 = SituationAssessment(
        aggregate_probability=0.4, source_weights={},
        consensus_score=0.2, stability=StabilityLevel.UNSTABLE,
        anomaly_flags=["x"], source_count=1,
    )
    assert sa2.is_consensus is False
    assert sa2.has_anomaly is True
    summary = sa.get_summary()
    assert summary["stability"] == "stable"
    assert summary["source_count"] == 2


def test_domain_normalize_weights_zero_total():
    """全部源权重为 0 时应退化为均匀权重。"""
    engine = DomainAwarenessEngine()
    sources = [
        _make_source("s1", 0.6, confidence=0.0),
        _make_source("s2", 0.4, confidence=0.0),
    ]
    assessment = engine.assess_situation(sources)
    assert abs(assessment.source_weights["s1"] - 0.5) < 1e-9
    assert abs(assessment.source_weights["s2"] - 0.5) < 1e-9


def test_domain_fuse_log_odds_negative_branch():
    """log_odds 融合 logit_sum < 0 分支（源概率普遍偏低）。"""
    engine = DomainAwarenessEngine()
    sources = [_make_source("s1", 0.2), _make_source("s2", 0.25), _make_source("s3", 0.15)]
    assessment = engine.assess_situation(sources, fusion_method="log_odds")
    assert assessment.fusion_method == "log_odds"
    assert 0.0 < assessment.aggregate_probability < 0.5


def test_domain_fuse_bayesian_negative_branch():
    """bayesian 融合 log_odds < 0 分支。"""
    engine = DomainAwarenessEngine()
    sources = [_make_source("s1", 0.2), _make_source("s2", 0.25), _make_source("s3", 0.15)]
    assessment = engine.assess_situation(
        sources, fusion_method="bayesian", prior_probability=0.5
    )
    assert assessment.fusion_method == "bayesian"
    assert 0.0 < assessment.aggregate_probability < 0.5


def test_domain_fuse_linear_method():
    """linear 融合方法分支。"""
    engine = DomainAwarenessEngine()
    sources = [_make_source("s1", 0.7), _make_source("s2", 0.5)]
    assessment = engine.assess_situation(sources, fusion_method="linear")
    assert assessment.fusion_method == "linear"
    assert 0.5 < assessment.aggregate_probability < 0.8


def test_domain_consensus_no_sources():
    """无源时 consensus 应为 0。"""
    engine = DomainAwarenessEngine()
    assert engine.calculate_consensus([], {}) == 0.0


def test_domain_detect_anomalies_zero_std():
    """所有源概率相同时 std=0 应返回空异常列表。"""
    engine = DomainAwarenessEngine()
    sources = [_make_source("s1", 0.5), _make_source("s2", 0.5), _make_source("s3", 0.5)]
    weights = {"s1": 1 / 3, "s2": 1 / 3, "s3": 1 / 3}
    assert engine.detect_anomalies(sources, weights) == []


def test_domain_detect_anomalies_with_outlier():
    """显著离群源应被标记为异常。"""
    engine = DomainAwarenessEngine()
    # 5 个 0.5 + 1 个 0.0，均匀权重 → 离群 z>2
    sources = [_make_source(f"s{i}", 0.5) for i in range(5)] + [_make_source("out", 0.0)]
    weights = {s.source_id: 1.0 / len(sources) for s in sources}
    anomalies = engine.detect_anomalies(sources, weights)
    assert "out" in anomalies


def test_domain_classify_stability_all_branches():
    """classify_stability 各分支。"""
    from edp import StabilityLevel

    engine = DomainAwarenessEngine()
    assert engine.classify_stability(0.9, 0) == StabilityLevel.STABLE
    assert engine.classify_stability(0.2, 0) == StabilityLevel.UNSTABLE
    assert engine.classify_stability(0.5, 0, momentum=3.0) == StabilityLevel.EMERGING
    assert engine.classify_stability(0.5, 0, momentum=1.0) == StabilityLevel.AMBIGUOUS
    assert engine.classify_stability(0.5, 1) == StabilityLevel.ANOMALOUS


def test_domain_assess_empty_sources():
    """无源时 assess_situation 应返回 AMBIGUOUS 评估。"""
    from edp import StabilityLevel

    engine = DomainAwarenessEngine()
    assessment = engine.assess_situation(
        [], prior_probability=0.4, fusion_method="linear"
    )
    assert assessment.aggregate_probability == 0.4
    assert assessment.stability == StabilityLevel.AMBIGUOUS
    assert assessment.source_count == 0
    assert assessment.confidence == 0.0


def test_domain_cross_validate_empty_group():
    """任一组为空时 cross_validate 应返回零一致度。"""
    engine = DomainAwarenessEngine()
    sources = [_make_source("s1", 0.6)]
    res = engine.cross_validate([], sources)
    assert res["agreement"] == 0.0
    assert res["combined"] is None
    res2 = engine.cross_validate(sources, [])
    assert res2["meta_confidence"] == 0.0


def test_domain_cross_validate_nonempty():
    """两组非空时 cross_validate 应返回一致性指标。"""
    engine = DomainAwarenessEngine()
    group_a = [_make_source("a1", 0.7), _make_source("a2", 0.68)]
    group_b = [_make_source("b1", 0.65), _make_source("b2", 0.66)]
    res = engine.cross_validate(group_a, group_b)
    assert 0.0 <= res["agreement"] <= 1.0
    assert res["delta"] >= 0.0
    assert res["combined"] is not None
    assert "group_a_probability" in res
    assert "group_b_probability" in res


def test_domain_model_diversity_single_source():
    """单一源时 model_diversity 应返回基线值。"""
    res = DomainAwarenessEngine.model_diversity([_make_source("s1", 0.5)])
    assert res["mean_pairwise_distance"] == 0.0
    assert res["effective_sources"] == 1.0
    assert res["diversity"] == 1.0


# ----------------------------------------------------------------------
# 补充测试：edp.py 覆盖率提升
# ----------------------------------------------------------------------


def test_edp_ingest_signals_no_quotes():
    """raw_data 非字典时 ingest_signals 应直接返回。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.initialize()
    edp.ingest_signals(None)
    assert set(edp.probabilities.keys()) == {"a", "b"}


def test_edp_ingest_signals_direct_probability_quotes():
    """probability 类型信号应走 direct_probs 路径并归一化。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.initialize()
    # 两条 probability 信号，总和 > 1.05 → 触发归一化
    edp.ingest_signals({"a": (0.8, "probability"), "b": (0.8, "probability")})
    assert abs(sum(edp.probabilities.values()) - 1.0) < 1e-6
    assert abs(edp.probabilities["a"] - 0.5) < 1e-6


def test_edp_ingest_signals_backfill_from_direct_probs():
    """混合 decimal_odds 与 probability 应触发缺失结果回填。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B"), Outcome("c", "C")])
    edp = EDP(domain)
    edp.initialize()
    # a 用 decimal_odds，b/c 用 probability → b/c 回填进 decimal_quotes
    edp.ingest_signals({
        "a": (2.0, "decimal_odds"),
        "b": (0.4, "probability"),
        "c": (0.2, "probability"),
    })
    assert abs(sum(edp.probabilities.values()) - 1.0) < 1e-6


def test_edp_add_evidence_empty():
    """空证据列表应返回 AMBIGUOUS 评估。"""
    from edp import StabilityLevel

    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.initialize()
    assessment = edp.add_evidence([])
    assert assessment.stability == StabilityLevel.AMBIGUOUS
    assert assessment.source_count == 0


def test_edp_add_evidence_unknown_source_type():
    """未知 source_type 应映射为 UNKNOWN。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.initialize()
    edp.add_evidence([
        Evidence("e1", "rumor", {"probability": 0.7}, outcome_id="a", confidence=0.6),
    ])
    assert edp.probabilities["a"] > 0.5


def test_edp_add_evidence_zero_weight_source_skipped():
    """confidence=0 的源归一化后权重为 0 应被跳过。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.initialize()
    edp.add_evidence([
        Evidence("e0", "model", {"probability": 0.9}, outcome_id="a", confidence=0.0),
        Evidence("e1", "expert", {"probability": 0.6}, outcome_id="a", confidence=0.8),
    ])
    assert edp.probabilities["a"] > 0.5


def test_edp_match_reliability_all_levels():
    """_match_reliability 应覆盖所有等级。"""
    from edp import SourceReliability

    assert EDP._match_reliability(0.95) == SourceReliability.A
    assert EDP._match_reliability(0.7) == SourceReliability.B
    assert EDP._match_reliability(0.5) == SourceReliability.C
    assert EDP._match_reliability(0.3) == SourceReliability.D
    assert EDP._match_reliability(0.1) == SourceReliability.E


def test_edp_analyze_amplification_without_flow():
    """flow 为 None 时 analyze_amplification 应返回 None。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.initialize()
    assert edp.analyze_amplification(None) is None


def test_edp_evaluate_and_conformal_update():
    """evaluate 与 conformal_update 应正确委托子引擎。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain, {"conformal": {"method": "aci", "alpha": 0.1}})
    edp.initialize()
    edp.ingest_signals({"a": (2.0, "decimal_odds"), "b": (2.0, "decimal_odds")})
    result = edp.evaluate("a")
    assert "brier_score" in result
    assert "top1_correct" in result
    upd = edp.conformal_update("a")
    assert "covered" in upd
    assert "coverage_rate" in upd


def test_edp_ingest_signals_value_error_fallback():
    """Shin 归一化抛 ValueError 时应回退到直接概率路径。"""
    domain = GenericDomain([Outcome("a", "A"), Outcome("b", "B")])
    edp = EDP(domain)
    edp.initialize()
    # b 用 probability=1.0，回填后 decimal_quotes["b"]=1.0/1.0=1.0，
    # 触发 calculate_true_probability 的 ValueError，走 except 回退分支。
    edp.ingest_signals({"a": (2.0, "decimal_odds"), "b": (1.0, "probability")})
    assert abs(sum(edp.probabilities.values()) - 1.0) < 1e-6
    assert set(edp.probabilities.keys()) == {"a", "b"}


def test_conformal_agaci_update_weights_empty_window():
    """_update_agaci_weights 在误差窗口为空时应使用 target 作为 rate。"""
    engine = ConformalEngine(ConformalConfig(method="agaci", alpha=0.1))
    # 初始化后所有 gamma 的误差列表为空，直接调用应覆盖空窗口分支
    engine._update_agaci_weights()
    total = sum(engine._agaci_weights.values())
    assert abs(total - 1.0) < 1e-9
    # 权重应均匀分布（所有 gamma 得分相同 → softmax 均匀）
    n = len(engine._agaci_weights)
    for w in engine._agaci_weights.values():
        assert abs(w - 1.0 / n) < 1e-9


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
