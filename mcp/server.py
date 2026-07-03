#!/usr/bin/env python3
"""
EDP MCP Server - Model Context Protocol Server (V2.0)

为 AI 助手暴露 EDP V2.0 的核心分析能力。

提供的工具：
    - analyze_situation: 一键分析（L0→L7 完整流程）
    - calculate_true_probability: Shin 归一化提取真实概率
    - assess_situation: 多源情报融合
    - conformal_predict: 保形预测集（有限样本覆盖率保证）
    - online_aggregate: 在线专家聚合
    - evaluate_prediction: 预测校准评估

⚠️ 风险警示 ⚠️
    本服务仅供学术研究与教育用途。所有输出不构成任何投资建议、
    决策建议或交易指导。使用者须自行承担一切决策风险。
"""

import json
import os
import sys
from typing import Any

# 将 src/python 加入路径
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src", "python"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# 以 edp 包名加载
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "edp", os.path.join(_SRC, "__init__.py"),
    submodule_search_locations=[_SRC],
)
_edp = importlib.util.module_from_spec(_spec)
sys.modules["edp"] = _edp
_spec.loader.exec_module(_edp)

from edp import (  # noqa: E402
    EDP,
    GenericDomain,
    Outcome,
    Evidence,
    ProbabilityEngine,
    DomainAwarenessEngine,
    OnlineAggregator,
    CalibrationEngine,
    ConformalEngine,
    ConformalConfig,
)


class EDPMCPServer:
    """
    EDP V2.0 MCP Server。

    暴露 EDP 的六层（+L7 保形层）分析能力给 AI 助手。

    ⚠️ 本服务仅供学术研究，输出不构成任何决策建议。
    """

    TOOLS = [
        "analyze_situation",
        "calculate_true_probability",
        "assess_situation",
        "conformal_predict",
        "online_aggregate",
        "evaluate_prediction",
    ]

    def __init__(self) -> None:
        self.prob_engine = ProbabilityEngine()
        self.domain_engine = DomainAwarenessEngine()
        self.calib_engine = CalibrationEngine()

    # ------------------------------------------------------------------
    # 工具实现
    # ------------------------------------------------------------------

    def analyze_situation(
        self,
        outcomes: list[dict[str, str]],
        evidence: list[dict[str, Any]] | None = None,
        raw_data: dict[str, float] | None = None,
        budget: float = 1000.0,
        return_multipliers: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """
        一键分析：L0→L7 完整流程。

        Args:
            outcomes: [{"id": "a", "label": "结果A"}, ...]
            evidence: [{"id":..., "source_type":..., "probability":...,
                        "outcome_id":..., "confidence":...}, ...]
            raw_data: {outcome_id: decimal_quote}（市场报价）
            budget: 分配预算
            return_multipliers: {outcome_id: return_multiplier}
        """
        domain = GenericDomain([Outcome(o["id"], o.get("label", o["id"])) for o in outcomes])
        edp = EDP(domain)
        ev_list = None
        if evidence:
            ev_list = [
                Evidence(
                    id=e["id"],
                    source_type=e["source_type"],
                    content={"probability": e.get("probability", 0.5)},
                    outcome_id=e.get("outcome_id"),
                    confidence=e.get("confidence", 0.7),
                    reliability=e.get("reliability", 0.8),
                )
                for e in evidence
            ]
        result = edp.analyze(
            raw_data=raw_data,
            evidence=ev_list,
            budget=budget,
            return_multipliers=return_multipliers,
        )
        # 序列化为 JSON 友好结构
        return {
            "probabilities": result["probabilities"],
            "summary": result["summary"],
            "prediction_set": result["prediction_set"].prediction_set,
            "coverage_target": result["prediction_set"].coverage_target,
            "allocation": result["allocation"].get_summary(),
            "warnings": result["warnings"],
        }

    def calculate_true_probability(
        self, quotes: dict[str, float]
    ) -> dict[str, Any]:
        """Shin 归一化：从市场报价提取真实概率。"""
        result = self.prob_engine.calculate_true_probability(quotes)
        return {
            "true_probabilities": result.true_probabilities,
            "implied_probabilities": result.implied_probabilities,
            "market_margin": result.market_margin,
            "method": result.method,
        }

    def assess_situation(
        self, sources: list[dict[str, Any]], prior_probability: float = 0.5
    ) -> dict[str, Any]:
        """多源情报融合。"""
        from edp import EvidenceSource, EvidenceType, SourceReliability
        from datetime import datetime
        src_objs = []
        for s in sources:
            try:
                etype = EvidenceType(s.get("evidence_type", "unknown"))
            except ValueError:
                etype = EvidenceType.UNKNOWN
            rel_weight = s.get("reliability_weight", 0.5)
            rel = SourceReliability.A if rel_weight >= 0.9 else (
                SourceReliability.B if rel_weight >= 0.7 else (
                    SourceReliability.C if rel_weight >= 0.5 else SourceReliability.D
                )
            )
            src_objs.append(EvidenceSource(
                source_id=s["source_id"],
                evidence_type=etype,
                reliability=rel,
                timestamp=datetime.now(),
                data={"probability": s.get("probability", 0.5)},
                confidence=s.get("confidence", 0.7),
            ))
        assessment = self.domain_engine.assess_situation(
            src_objs, prior_probability=prior_probability
        )
        return assessment.get_summary()

    def conformal_predict(
        self,
        predictions: dict[str, float],
        alpha: float = 0.1,
        method: str = "aci",
    ) -> dict[str, Any]:
        """保形预测集（有限样本覆盖率保证）。"""
        engine = ConformalEngine(ConformalConfig(alpha=alpha, method=method))
        pset = engine.predict(predictions)
        return {
            "prediction_set": pset.prediction_set,
            "coverage_target": pset.coverage_target,
            "threshold": pset.threshold,
            "method": pset.method,
        }

    def online_aggregate(
        self,
        predictions: list[dict[str, float]],
        actuals: list[float],
        algorithm: str = "online_bayesian_stacking",
    ) -> dict[str, Any]:
        """在线专家聚合。"""
        agg = OnlineAggregator({"algorithm": algorithm})
        source_ids = list(predictions[0].keys())
        agg.initialize(source_ids)
        for preds, actual in zip(predictions, actuals):
            agg.predict(preds)
            agg.update(preds, actual)
        return {
            "weights": agg.get_weights(),
            "performance": agg.get_performance(),
        }

    def evaluate_prediction(
        self,
        predictions: dict[str, float],
        actual_outcome: str,
    ) -> dict[str, Any]:
        """预测校准评估（Brier + Log + Hyvärinen）。"""
        eval_result = self.calib_engine.evaluate(predictions, actual_outcome)
        eval_result["hyvarinen_score"] = self.calib_engine.hyvarinen_score(
            predictions, actual_outcome
        )
        return eval_result

    # ------------------------------------------------------------------
    # MCP 协议入口（占位，实际需接 mcp SDK）
    # ------------------------------------------------------------------

    def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """处理工具调用，返回 JSON 字符串。"""
        handler = getattr(self, tool_name, None)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            result = handler(**arguments)
            return json.dumps(result, default=str, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            return json.dumps({"error": str(e)}, ensure_ascii=False)


def main() -> None:
    """命令行入口：打印可用工具列表。"""
    server = EDPMCPServer()
    print("EDP MCP Server V2.0 — 可用工具：")
    for t in server.TOOLS:
        print(f"  - {t}")
    print("\n⚠️ 仅供学术研究，不构成任何决策建议。")


if __name__ == "__main__":
    main()
