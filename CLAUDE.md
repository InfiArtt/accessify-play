@DEVELOPMENT.md

## Working on this repository

* The owner is blind and uses NVDA. Write to them in Dutch, with headings and short lists rather than tables.
* Before finishing a change, run `ruff check .`, `ruff format --check .`, `pyright` and `python -m pytest --cov`, and add or update tests in `tests/unit` for what changed.
* Values that could differ between users or setups go in the table in `settings_spec.py`, not in the code (see "How the code works" in DEVELOPMENT.md).
* Every user-visible change goes into `CHANGELOG.md` under `## Unreleased`, and into the user guides in both `addon/doc/en` and `addon/doc/id`.
