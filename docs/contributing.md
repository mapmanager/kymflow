# Contributing

Thank you for your interest in contributing to KymFlow!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/mapmanager/kymflow.git
   cd kymflow
   ```

2. Install in editable mode with development dependencies:
   ```bash
   pip install -e ".[gui,test,notebook]"
   ```

3. Run tests:
   ```bash
   pytest
   ```

## Code Style

- Follow PEP 8 style guidelines
- Use type hints for function parameters and return values
- Add docstrings in Google style format
- Run linters before submitting PRs

## Testing

- Write tests for new features
- Ensure all tests pass: `pytest`
- Aim for good test coverage of new code
- Tests should work without proprietary data when possible

## Documentation

- Update docstrings when adding/changing functions
- Update user guide for GUI changes
- Update API docs for backend changes
- Keep examples in notebooks up to date

## Submitting Changes

1. Create a feature branch
2. Make your changes
3. Add/update tests
4. Run tests and ensure they pass
5. Submit a pull request with a clear description
