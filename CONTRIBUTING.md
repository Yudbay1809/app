# Contributing

Thanks for contributing to this project.

## Setup
1. Use Python 3.13.
2. Create or activate virtual environment.
3. Install dependencies:
   - `python -m pip install -r requirements.txt`

## Local Validation
Run before opening a PR:
- `python -m compileall api models schemas services main.py db.py seed.py`
- `python -c "import pathlib, sys, types; pkg = types.ModuleType('app'); pkg.__path__ = [str(pathlib.Path('.').resolve())]; sys.modules['app'] = pkg; import app.main"`

## Pull Request Checklist
- [ ] Change is focused and small.
- [ ] Documentation updated if behavior changed.
- [ ] API behavior validated locally.

## Commit Messages
Use clear commit messages, for example:
- `feat: add device ownership validation`
- `fix: prevent duplicate playlist item ordering`
- `chore: update backend CI workflow`
