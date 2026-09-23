"""Command line entry point: ``openmeteo-downloader <command>``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .client import DEFAULT_URL, Client, ServerNotRunningError
from .config import run_job, template


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openmeteo-downloader",
        description="Fast ERA5 downloads from a local Open-Meteo server.",
        epilog="Typical first run:  compose  ->  docker compose up -d  ->  init  ->  run config.toml",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    init = commands.add_parser("init", help="write an example job file to edit")
    init.add_argument("path", nargs="?", default="config.toml", type=Path)
    init.add_argument("--force", action="store_true", help="overwrite an existing file")

    compose = commands.add_parser("compose", help="write the docker-compose.yml for the server")
    compose.add_argument("folder", nargs="?", default=".", type=Path)
    compose.add_argument("--force", action="store_true", help="overwrite an existing file")

    check = commands.add_parser("check", help="check the Open-Meteo server is running")
    check.add_argument("--server", default=DEFAULT_URL)

    run = commands.add_parser("run", help="download everything described in a job file")
    run.add_argument("config", type=Path)
    run.add_argument("-q", "--quiet", action="store_true", help="no progress output")

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            _write(args.path, template("config.toml"), args.force)
            print(f"Edit {args.path}, then run:  openmeteo-downloader run {args.path}")
        elif args.command == "compose":
            path = args.folder / "docker-compose.yml"
            _write(path, template("docker-compose.yml"), args.force)
            print(f"Start the server from {args.folder.resolve()} with:  docker compose up -d")
        elif args.command == "check":
            Client(args.server).ensure_running()
            print(f"Open-Meteo server is up at {args.server}")
        elif args.command == "run":
            for path in run_job(args.config, progress=not args.quiet):
                print(f"Wrote {path}")
    except (ServerNotRunningError, FileExistsError, FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists (use --force to overwrite)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    sys.exit(main())
