@DEVELOPMENT.md

## Working on this repository

* The owner is blind and uses NVDA. Write to them in Dutch, with headings and short lists rather than tables.
* Before finishing a change, run `ruff check .`, `ruff format --check .`, `python tests/run_tests.py` and `python -m pytest --cov`, and add or update tests in `tests/unit` for what changed.
* Every user-visible change goes into `CHANGELOG.md` under `## Unreleased`, and into the user guides in both `addon/doc/en` and `addon/doc/id`.
