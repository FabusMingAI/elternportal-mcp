"""CLI entry point; stdout is reserved for MCP JSON-RPC."""

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .config import load_settings
from .server import create_server
from .service import Service


def main():
    parser = argparse.ArgumentParser(description="Local Eltern-Portal MCP server (stdio)")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", type=Path, help="Path to a private JSON configuration")
    parser.add_argument("--demo", action="store_true", help="Synthetic data; no account or network")
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    # Upstream error/debug messages can contain portal HTML; do not forward them to MCP logs.
    logging.getLogger("pyelternportal").disabled = True
    try:
        settings = load_settings(args.config, demo=args.demo)
        for school in settings.schools:
            school.password()
    except Exception:
        parser.exit(
            2, "Invalid configuration or missing credentials. See README.md; no secrets logged.\n"
        )
    service = Service(settings)
    try:
        create_server(service).run(transport="stdio")
    finally:
        service.store.close()


if __name__ == "__main__":
    main()
