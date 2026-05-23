# Common dev operations for dockerctx.
# Run `just` (or `just --list`) to see available recipes.

# Show available recipes.
default:
    @just --list

# Sync the venv with all locked dev/test dependencies.
sync:
    uv sync --group test

# Run the test suite. Requires a running Docker daemon.
test:
    uv run pytest tests/

# Run tests with coverage (lcov output for coveralls).
coverage:
    uv run pytest --cov=dockerctx --cov-report=lcov:coverage.lcov tests/

# Bump + tag + push a release. Pushing a v* tag triggers PyPI publish.
# Usage: `just release patch` (or minor / major).
release *bump:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -n "$(git status --porcelain)" ]]; then
        echo "error: working tree is dirty; commit or stash first" >&2
        exit 1
    fi
    uv version --bump {{bump}}
    new_version=$(uv version --short)
    git commit -am "Bump to ${new_version}"
    git tag "v${new_version}"
    git push --follow-tags
    echo "released v${new_version}"
