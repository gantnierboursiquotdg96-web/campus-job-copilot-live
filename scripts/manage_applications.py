"""Revision-checked local application CSV management."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple


FIELDS = [
    "opportunity_id",
    "company",
    "roles_raw",
    "status",
    "added_at",
    "updated_at",
    "notes",
    "application_url",
    "announcement_url",
]
HEADER_LINE = ",".join(FIELDS) + "\n"
STATUSES = ("待评估", "待投递", "已投递", "笔试", "面试", "淘汰", "Offer")


class ApplicationDataError(RuntimeError):
    pass


class RevisionConflictError(ApplicationDataError):
    pass


def read_records(path: Path) -> Tuple[List[dict], str]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise ApplicationDataError(f"Cannot read applications CSV: {path}") from exc
    revision = hashlib.sha256(raw).hexdigest()
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != FIELDS:
        raise ApplicationDataError("Applications CSV has an invalid header")
    records = []
    try:
        for row in reader:
            if (
                None in row
                or any(row.get(field) is None for field in FIELDS)
                or not row.get("opportunity_id")
                or row.get("status") not in STATUSES
            ):
                raise ApplicationDataError("Applications CSV contains a malformed row")
            records.append(dict(row))
    except csv.Error as exc:
        raise ApplicationDataError("Applications CSV contains malformed CSV") from exc
    return records, revision


def _atomic_write(path: Path, records: List[dict]) -> str:
    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=str(path.parent), prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    except OSError as exc:
        detail = f"; temporary file retained at {temporary}" if temporary else ""
        raise ApplicationDataError(f"Cannot update applications CSV: {path}{detail}") from exc
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validated_records(path: Path, expected_revision: str) -> List[dict]:
    records, current = read_records(path)
    if current != expected_revision:
        raise RevisionConflictError("Applications CSV revision changed; reload before updating")
    return records


def add_record(path: Path, opportunity: dict, status: str, notes: str, expected_revision: str) -> str:
    records = _validated_records(path, expected_revision)
    if status not in STATUSES:
        raise ApplicationDataError(f"Invalid application status: {status}")
    if not isinstance(opportunity, dict):
        raise ApplicationDataError("Opportunity JSON must be an object")
    opportunity_id = opportunity.get("opportunity_id")
    if not isinstance(opportunity_id, str) or not opportunity_id:
        raise ApplicationDataError("Opportunity requires opportunity_id")
    if any(row["opportunity_id"] == opportunity_id for row in records):
        raise ApplicationDataError(f"Duplicate opportunity_id: {opportunity_id}")
    now = datetime.now(timezone.utc).isoformat()
    records.append({
        "opportunity_id": opportunity_id, "company": opportunity.get("company") or "",
        "roles_raw": opportunity.get("roles_raw") or "", "status": status,
        "added_at": now, "updated_at": now, "notes": notes,
        "application_url": opportunity.get("application_url") or "",
        "announcement_url": opportunity.get("announcement_url") or "",
    })
    return _atomic_write(path, records)


def update_record(path: Path, opportunity_id: str, status: Optional[str], notes: Optional[str], expected_revision: str) -> str:
    records = _validated_records(path, expected_revision)
    if status is not None and status not in STATUSES:
        raise ApplicationDataError(f"Invalid application status: {status}")
    matched = False
    for row in records:
        if row["opportunity_id"] == opportunity_id:
            matched = True
            if status is not None:
                row["status"] = status
            if notes is not None:
                row["notes"] = notes
            row["updated_at"] = datetime.now(timezone.utc).isoformat()
    if not matched:
        raise ApplicationDataError(f"Unknown opportunity_id: {opportunity_id}")
    return _atomic_write(path, records)


def render_report(records: List[dict]) -> str:
    lines = ["# 校招投递进度", ""]
    for status in STATUSES:
        rows = [row for row in records if row.get("status") == status]
        if not rows:
            continue
        lines.extend([f"## {status}", ""])
        for row in rows:
            lines.append(f"- {row.get('company') or '公司待确认'} | {row.get('roles_raw') or '岗位待确认'} | {row.get('notes') or '无备注'}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Manage local campus application records")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("list", "report"):
        command = sub.add_parser(name)
        command.add_argument("--file", type=Path, required=True)
        if name == "report":
            command.add_argument("--output", type=Path)
    add = sub.add_parser("add")
    add.add_argument("--file", type=Path, required=True)
    add.add_argument("--opportunity-json", type=Path, required=True)
    add.add_argument("--status", required=True)
    add.add_argument("--notes", default="")
    add.add_argument("--expected-revision", required=True)
    update = sub.add_parser("update")
    update.add_argument("--file", type=Path, required=True)
    update.add_argument("--opportunity-id", required=True)
    update.add_argument("--status")
    update.add_argument("--notes")
    update.add_argument("--expected-revision", required=True)
    args = parser.parse_args(argv)
    try:
        records, revision = read_records(args.file)
        if args.command == "list":
            output = {"records": records, "revision": revision}
        elif args.command == "add":
            opportunity = json.loads(args.opportunity_json.read_text(encoding="utf-8"))
            new_revision = add_record(
                args.file,
                opportunity,
                args.status,
                args.notes,
                args.expected_revision,
            )
            output = {"revision": new_revision}
        elif args.command == "update":
            new_revision = update_record(
                args.file,
                args.opportunity_id,
                args.status,
                args.notes,
                args.expected_revision,
            )
            output = {"revision": new_revision}
        else:
            report = render_report(records)
            if args.output:
                args.output.write_text(report, encoding="utf-8")
                output = {"output": str(args.output), "revision": revision}
            else:
                print(report, end="")
                return 0
        print(json.dumps(output, ensure_ascii=False))
        return 0
    except (ApplicationDataError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
