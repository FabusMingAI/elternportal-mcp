# Contributing

Use Python 3.13 or later and `pip install -e '.[dev]'`. Run the lint, formatting,
test and build commands from README.md before sending a pull request. CI runs on
Linux and Windows with Python 3.13 and 3.14.

Please include a synthetic/anonymized HTML fixture and a regression test for
parser fixes. Never upload a real exported portal page: HTML can contain hidden
student identifiers, CSRF values, names and signed download URLs even when the
visible text looks anonymous. Do not post credentials, school correspondence or
children's names in issues.

When adapting additional upstream code, preserve attribution and document the
source commit. Keep portal transport, pure parsers, local organization and MCP
tool definitions separate. The vendored parsers are excluded from style checks
to keep their relationship to upstream recognizable; regression tests still run.

Portal writes need a separate design with preview, consent, result verification
and duplicate-submission handling. Do not hide them inside a read-only tool.

Release process: update the version in pyproject.toml and `__init__.py`, update
CHANGELOG.md, run checks, build wheel/sdist, tag `vX.Y.Z`, then create a GitHub
release with both build artifacts and validation notes. PyPI publishing is not
configured in the initial release.
