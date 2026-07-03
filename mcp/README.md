# EDP MCP Server

Model Context Protocol (MCP) server for the **EDP V2.0** framework.

Exposes the seven-layer probabilistic situation-awareness engine to AI assistants
(MCP-compatible clients such as Claude Desktop).

## ⚠️ Disclaimer

**This server is for ACADEMIC RESEARCH AND EDUCATIONAL PURPOSES ONLY.**

It does NOT constitute any investment advice, decision-making advice, betting/gambling
advice, or financial planning advice. Users bear full responsibility for their own
decisions. See the top-level [README](../README.md) for the full risk warning.

---

## Available Tools (V2.0)

The server exposes six tools mapping to the EDP layers (L0 → L7):

| Tool | Layer | Description |
|------|-------|-------------|
| `analyze_situation` | L0–L7 | One-shot full analysis (domain + evidence + conformal + allocation) |
| `calculate_true_probability` | L1 | Shin normalization: extract true probabilities from quotes |
| `assess_situation` | L4 | Multi-source intelligence fusion (linear/log-odds/Bayesian) |
| `conformal_predict` | L7 | Conformal prediction set (finite-sample coverage guarantee) |
| `online_aggregate` | L2 | Online expert aggregation (ML-Poly / EWA / Ridge / Bayesian Stacking) |
| `evaluate_prediction` | L6 | Calibration scoring (Brier / Log / Hyvärinen) |

---

## Usage

### Run the server

```bash
git clone https://github.com/ai-nurmamat/EDP.git
cd EDP
python mcp/server.py
```

> The server is a reference implementation. To plug it into a full MCP host,
> wrap `EDPMCPServer.handle_tool_call` with your MCP SDK transport
> (stdio / HTTP / SSE).

### Example: `analyze_situation`

```json
{
  "outcomes": [
    {"id": "rain", "label": "下雨"},
    {"id": "no_rain", "label": "不下雨"}
  ],
  "evidence": [
    {"id": "model", "source_type": "model", "probability": 0.72,
     "outcome_id": "rain", "confidence": 0.8}
  ],
  "budget": 0
}
```

Returns:

```json
{
  "probabilities": {"rain": 0.68, "no_rain": 0.32},
  "prediction_set": ["rain"],
  "coverage_target": 0.9,
  "warnings": ["..."]
}
```

---

## Development

```bash
# Python setup (V2.0 authoritative implementation)
pip install -e ".[dev]"

# List available tools
python mcp/server.py
```

## License

MIT License — see the [LICENSE](../LICENSE) file for details.
