# Contributing to EDP

Thank you for your interest in contributing to the **Expectation Domain Perception Method (EDP)**!

## ⚠️ Important Notice

**This project is for ACADEMIC RESEARCH AND EDUCATIONAL PURPOSES ONLY.**

Contributions must align with this purpose. We do **not** accept contributions that:

- Promote or encourage gambling, betting, or any lottery-like activity as a way to make money
- Claim to "beat the system" or guarantee profits
- Frame the framework as financial/investment advice
- Violate any laws or regulations
- Encourage irresponsible behavior

## How to Contribute

### Reporting Issues

1. Check if the issue already exists in [Issues](https://github.com/ai-nurmamat/EDP/issues)
2. Open a new issue with a clear title and description
3. Provide reproduction steps and relevant environment details

### Submitting Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all checks pass (see below)
6. Commit with clear messages (conventional commits preferred)
7. Push to your branch
8. Open a Pull Request against `master`

### Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/EDP.git
cd EDP

# Python setup (V2.0 authoritative implementation)
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e ".[dev]"

# Run tests
pytest tests/python/
```

> **Note:** The TypeScript/JavaScript implementation under `src/js/` is a V1 (4.1.0)
> legacy port and has not been upgraded to the V2.0 seven-layer architecture. The
> Python package under `src/python/` is the authoritative V2.0 implementation.
> New feature work should target the Python package.

### Code Style

**Python (V2.0):**
- Follow PEP 8
- Use type hints throughout
- Maximum line length: 100 characters
- Format with `black` and `isort`
- Lint with `ruff`
- Type-check with `mypy --strict`

**Pre-commit checklist:**

```bash
black src/python/
isort src/python/
ruff check src/python/
mypy src/python/
pytest tests/python/
```

### Testing

- All new code must have tests under `tests/python/`
- Maintain or improve coverage
- Run `pytest tests/python/ -v` before submitting

### Documentation

- Update `README.md` if behavior changes
- Add docstrings to all public functions/classes
- Keep the seven-layer architecture description in sync with the code

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details.

## Security

If you discover a security vulnerability, please see [SECURITY.md](SECURITY.md)
and report it privately — do not open a public issue.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Open an issue for any questions about contributing.

---

Thank you for helping improve EDP!
