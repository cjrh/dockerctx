# Releasing

Releases are triggered by pushing a `v*` tag. PyPI publishing uses
[trusted publishing][tp] (OIDC), so no API tokens are stored in this repo.

## One-time PyPI setup

Configure the trusted publisher on PyPI **once** (project owners only):

1. Sign in to <https://pypi.org/manage/project/dockerctx/settings/publishing/>.
2. Add a new GitHub trusted publisher with:
   - Owner: `cjrh`
   - Repository: `dockerctx`
   - Workflow filename: `release.yml`
   - Environment: `pypi`
3. In this repo's GitHub settings, create an environment named `pypi`
   (Settings → Environments → New environment). No secrets are needed —
   the OIDC token from `id-token: write` is the credential.

## Cutting a release

From a clean working tree on `master`:

```sh
just release patch   # or minor / major
```

That recipe:

1. `uv version --bump <part>` (writes `pyproject.toml`)
2. `git commit -am "Bump to <new>"`
3. `git tag v<new>`
4. `git push --follow-tags`

Pushing the `v*` tag fires `.github/workflows/release.yml`, which builds
the sdist + wheel with `uv build` and publishes to PyPI.

Note: this project historically used CalVer (e.g. `2024.3.2`). `uv version
--bump patch` does the right thing for CalVer too (it increments the
trailing component). For a calendar rollover (`2024.3.2` → `2025.1.0`),
edit `pyproject.toml` by hand and commit, then tag.

[tp]: https://docs.pypi.org/trusted-publishers/
