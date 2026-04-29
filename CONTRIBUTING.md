# Contributing to VoidAccess

Thank you for your interest in contributing to VoidAccess!

## Development Setup

1. **Fork** the repository on GitHub
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/voidaccess.git
   cd voidaccess
   ```

3. **Create a virtual environment** and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   pip install -r dev-requirements.txt
   python -m spacy download en_core_web_sm
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the tests** to verify your setup:
   ```bash
   pytest tests/
   ```

## Code Style

- **Black** for code formatting (run `black .`)
- **isort** for import sorting (run `isort .`)
- **ruff** for linting (run `ruff check .`)
- **type hints** are required for new functions

## Branch Workflow

1. Create a new branch for your feature or fix:
   ```bash
   git checkout -b feature/my-new-feature
   # or
   git checkout -b fix/bug-description
   ```

2. Make your changes and commit:
   ```bash
   git add changed_files.py
   git commit -m "Description of changes"
   ```

3. Push to your fork and create a Pull Request:
   ```bash
   git push origin feature/my-new-feature
   ```

## Running Tests

```bash
# All tests
pytest tests/

# Specific test file
pytest tests/test_api.py

# With coverage
pytest tests/ --cov=. --cov-report=term-missing
```

## Adding New Dependencies

If you add a new dependency:
1. Add it to `requirements.in` (unpinned)
2. Run `pip-compile requirements.in --output-file requirements.txt`
3. Commit both files

## Questions?

- Open an issue on GitHub for bugs or feature requests
- For security issues, see SECURITY.md

We welcome contributions from the community!