# Contributing

## Development setup

```zsh
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e '.[release]'
```

Run tests before pushing:

```zsh
python -m unittest discover -s tests -v
```

## Commit message format

This repository uses Conventional Commits so semantic-release can calculate the next version automatically.

Examples:

- `feat: add preset for light backgrounds`
- `fix: keep punctuation in content mask`
- `perf: reduce preview render time`
- `docs: clarify local setup`
- `feat!: change saved params schema`

Breaking changes can also be declared with a footer:

```text
BREAKING CHANGE: explain the incompatible behavior change here
```

## Release behavior

- `feat` triggers a minor release
- `fix`, `perf`, and `refactor` trigger a patch release
- `docs`, `test`, `ci`, `build`, `style`, and `chore` do not trigger a release by default
- `!` or a `BREAKING CHANGE:` footer triggers a breaking release

## GitHub Actions release flow

Pushes to `main` trigger `.github/workflows/release.yml`.

That workflow:

1. installs project and release dependencies
2. runs the test suite
3. runs semantic-release
4. updates `pyproject.toml` and `CHANGELOG.md`
5. creates the tag and GitHub Release

