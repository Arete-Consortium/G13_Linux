# G13 Release Checklist

Use this checklist for every `g13-linux` release.

## 1. Version and tag alignment

1. Confirm `project.version` in `pyproject.toml`.
2. Update `CHANGELOG.md` — promote `[Unreleased]` entries to `[X.Y.Z] - YYYY-MM-DD`.
3. Use a `vX.Y.Z` tag format (for example: `v1.7.0`).
4. Ensure the tag version matches `pyproject.toml` exactly.

## 2. Release gate validation

1. Run tests locally:
   - `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/`
2. Run Ubuntu parity tests locally when possible:
   - `./scripts/test_ubuntu.sh --system-deps`
3. Verify lint + format:
   - `ruff check src/ tests/ && ruff format --check src/ tests/`
4. Build artifacts locally to catch errors before tagging:
   - `python -m build && twine check dist/*`
5. Ensure CI is green on `main` before tagging.

## 3. Trusted Publishing (PyPI) configuration

If PyPI publish fails with `invalid-publisher`, configure (or update) the Trusted Publisher on PyPI with these exact values:

- Owner: `AreteDriver`
- Repository: `G13_Linux`
- Workflow file: `.github/workflows/release.yml`
- Environment (recommended): `pypi`

Notes:
- The workflow filename must match exactly.
- The workflow uses `id-token: write` and `environment: pypi`, which must match PyPI publisher configuration.

Reference docs:
- PyPI: [Adding a Trusted Publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- PyPI: [Trusted Publisher troubleshooting](https://docs.pypi.org/trusted-publishers/troubleshooting/)

## 4. Publish and verify artifacts

1. Push `main`.
2. Create and push release tag:
   - `git tag -a vX.Y.Z -m "vX.Y.Z — short summary"`
   - `git push origin vX.Y.Z`
3. Verify the `Release` workflow run:
   - test gate passes
   - AppImage build passes
   - GitHub release is created with:
     - `.whl`
     - `.tar.gz`
     - `.AppImage`
4. Verify PyPI publish status: `pip index versions g13-linux` should list the new version within ~1 minute.

## 5. Post-release checks

1. Validate release page assets download correctly.
2. Smoke test install on Ubuntu:
   - `pip install g13-linux==X.Y.Z`
3. Hardware smoke test if any device-facing changes shipped (see `docs/testing-ubuntu.md`).
4. Confirm docs/examples still reflect current joystick schema and setup flow.
