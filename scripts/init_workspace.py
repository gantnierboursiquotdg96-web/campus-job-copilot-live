"""Create the local Campus Job Assistant workspace without overwriting data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


PROFILE = '{"schema_version":1,"profile":null,"resume_summary":null}\n'
APPLICATION_HEADER = "opportunity_id,company,roles_raw,status,added_at,updated_at,notes,application_url,announcement_url\n"


def _create_exclusive(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="") as handle:
            handle.write(content)
    except FileExistsError:
        pass


def initialize_workspace(root: Path) -> Dict[str, str]:
    root = root.expanduser()
    try:
        root.mkdir(parents=True, exist_ok=True)
        reports = root / "reports"
        reports.mkdir(exist_ok=True)
        profile = root / "profile.json"
        applications = root / "applications.csv"
        _create_exclusive(profile, PROFILE)
        _create_exclusive(applications, APPLICATION_HEADER)
    except OSError as exc:
        raise RuntimeError(f"Cannot initialize workspace at {root}: {exc}") from exc
    return {"root": str(root), "profile": str(profile), "applications": str(applications), "reports": str(reports)}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("~/Documents/CampusJobAssistant"))
    args = parser.parse_args(argv)
    try:
        print(json.dumps(initialize_workspace(args.root), ensure_ascii=False))
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
