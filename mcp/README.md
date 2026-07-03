# EDP MCP Server

Model Context Protocol (MCP) server for the EDP framework.

## ⚠️ Disclaimer

**This server is for ACADEMIC RESEARCH AND EDUCATIONAL PURPOSES ONLY.**

This framework is for probability analysis and statistical research. No system can guarantee results.

## Installation

```bash
pip install edp-mcp-server
```

## Configuration

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "edp": {
      "command": "edp-mcp-server",
      "args": []
    }
  }
}
```

## Available Tools

### `calculate_true_probability`

Calculate true probabilities from market quotes by removing the margin.

**Parameters:**
- `quotes` (object): Dictionary mapping outcomes to decimal values

**Example:**
```json
{
  "quotes": {
    "home": 1.50,
    "draw": 4.20,
    "away": 6.00
  }
}
```

**Returns:**
```json
{
  "true_probabilities": {
    "home": 0.632,
    "draw": 0.226,
    "away": 0.158
  },
  "margin": 0.054
}
```

---

### `analyze_flow`

Analyze probability flow between two time points.

**Parameters:**
- `initial_probabilities` (object): Initial probability snapshot
- `latest_probabilities` (object): Latest probability snapshot
- `market_type` (string, optional): Market type (default: "1X2")

**Returns:**
- Flow report with direction and significance for each outcome

---

### `calculate_amplification`

Calculate amplification effect for probability flows.

**Parameters:**
- `flow_report` (object): Flow analysis report
- `gradient_map` (object): Map of outcomes to adjacent outcomes
- `outcome_probabilities` (object): Current true probabilities
- `domain_confidence` (object, optional): Confidence scores from domain awareness

**Returns:**
- Amplification report with scores and levels

---

### `validate_scheme`

Validate a scheme against Three Principles and rules.

**Parameters:**
- `legs` (array): List of scheme legs
- `multiplier` (integer, optional): Multiplier (default: 1)
- `allocation_per_combination` (number, optional): Allocation amount (default: 2.0)

**Returns:**
- Validation result with any errors

---

### `generate_schemes`

Generate optimized schemes within budget.

**Parameters:**
- `amplification_report` (object): Amplification report
- `budget` (number): Total budget to allocate
- `scenario_data` (object): Scenario information
- `max_schemes` (integer, optional): Maximum schemes to generate (default: 10)

**Returns:**
- Scheme bundle with optimized schemes

## Usage with AI Assistants

Once configured, you can use natural language to interact with the EDP framework:

```
User: Calculate the true probability for quotes home 1.5, draw 4.2, away 6.0

AI: I'll calculate the true probabilities by removing the market margin...

[Calls calculate_true_probability tool]

The true probabilities are:
- Home: 63.2%
- Draw: 22.6%
- Away: 15.8%

The market margin is 5.4%.
```

## Development

```bash
# Clone repository
git clone https://github.com/ai-nurmamat/EDP.git
cd EDP/mcp

# Install dependencies
pip install -e ".[dev]"

# Run server
python server.py
```

## License

MIT License - See LICENSE file for details.

## Disclaimer

**This server is for ACADEMIC RESEARCH AND EDUCATIONAL PURPOSES ONLY.**

- This server does not constitute any investment advice or decision-making advice.
- Any decisions made using this server are the user's sole responsibility.
- The author is not responsible for any losses incurred through use of this server.
- Please comply with laws and regulations in your jurisdiction.
