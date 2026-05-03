# G13 Release Checklist

Use this checklist for every `g13-linux` release from the `LinuxTools` monorepo.

## 1. Version and tag alignment

1. Confirm `project.version` in `g13/pyproject.toml`.
2. Update `g13/CHANGELOG.md`.
3. Use a `g13-vX.Y.Z` tag format (for example: `g13-v1.5.7`).
4. Ensure the tag version matches `pyproject.toml` exactly.

## 2. Release gate validation

1. Run Ubuntu parity tests locally when possible:
   - `./scripts/test_ubuntu.sh --system-deps`
2. Confirm root workflow files are present:
   - `.github/workflows/g13-ci.yml`
   - `.github/workflows/g13-release.yml`
3. Ensure `G13: CI` is green before or alongside the tag push.

## 3. Trusted Publishing (PyPI) configuration

If PyPI publish fails with `invalid-publisher`, configure (or update) the Trusted Publisher on PyPI with these exact values:

- Owner: `AreteDriver`
- Repository: `LinuxTools`
- Workflow file: `.github/workflows/g13-release.yml`
- Environment (recommended): `pypi`

Notes:
- The workflow filename must match exactly.
- If you changed from a previous repo/path (for example legacy single-project repos), update PyPI publisher settings to this monorepo workflow.
- The workflow uses `id-token: write` and `environment: pypi`, which must match PyPI publisher configuration.

Reference docs:
- PyPI: [Adding a Trusted Publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- PyPI: [Trusted Publisher troubleshooting](https://docs.pypi.org/trusted-publishers/troubleshooting/)

## 4. Publish and verify artifacts

1. Push `main`.
2. Create and push release tag:
   - `git tag -a g13-vX.Y.Z -m "g13-linux vX.Y.Z"`
   - `git push origin g13-vX.Y.Z`
3. Verify `G13: Release` run:
   - test gate passes
   - AppImage build passes
   - GitHub release is created with:
     - `.whl`
     - `.tar.gz`
     - `.AppImage`
4. Verify PyPI publish status.
   - If Trusted Publisher is still not configured, GitHub release artifacts still publish, but PyPI upload will warn and be skipped.

## 5. Post-release checks

1. Validate release page assets download correctly.
2. Smoke test install on Ubuntu:
   - `pip install g13-linux==X.Y.Z`
3. Confirm docs/examples still reflect current joystick schema and setup flow.
