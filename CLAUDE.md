# ArenaHub: guidelines for Claude

## Git

- **Never commit automatically.** Leave changes uncommitted unless the user
  explicitly asks for a commit in that request. The same goes for pushing,
  tagging and creating releases.

## Language

- The user may write in Spanish, but code, comments, UI texts, commit messages
  and repository docs (README, workflow messages) are in English.

## Dependencies and environment

- Add every library with `uv add` so that `pyproject.toml` and `uv.lock` stay
  in sync. If it is imported dynamically or only on one platform, also wire it
  into `ArenaHub.spec`: the `REQUIRED` import check, plus `hiddenimports`,
  `datas` or `binaries` as needed.
- `scripts/setup_*` must always work, including on machines with no Python
  installed. Use only the uv-managed Python, never a system or global one.
- Production is a single PyInstaller onefile binary that needs no Python on
  the target machine.

## Before calling a change done

```bash
uv run ruff check src tests scripts && uv run ruff format --check src tests scripts
uv run pytest
uv run pyinstaller ArenaHub.spec --clean --noconfirm   # when dependencies or the spec change
uv run python scripts/package.py --verify-only         # checks the frozen binary
```

- Update `README.md` whenever behaviour, requirements or the project layout
  change.
