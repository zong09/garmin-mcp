"""CLI: `garmin-mcp login` authenticates, `garmin-mcp serve` runs the MCP server."""

from __future__ import annotations

import sys


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "login":
        from .auth import login

        login()
    elif command == "serve":
        from .server import serve

        serve()
    else:
        print("usage: garmin-mcp {login|serve}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
