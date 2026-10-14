"""Load and validate the bundled campus opportunity dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple


class DatasetIntegrityError(RuntimeError):
    """Raised when bundled dataset assets fail integrity checks."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DatasetIntegrityError(f"Cannot read a valid dataset manifest: {path}") from exc

    if not isinstance(manifest, dict):
        raise DatasetIntegrityError("Dataset manifest must be a JSON object")

    record_count = manifest.get("record_count")
    if (
        not isinstance(record_count, int)
        or isinstance(record_count, bool)
        or record_count < 0
    ):
        raise DatasetIntegrityError("Dataset manifest has an invalid record_count")

    expected_hash = manifest.get("sha256")
    if (
        not isinstance(expected_hash, str)
        or len(expected_hash) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in expected_hash)
    ):
        raise DatasetIntegrityError("Dataset manifest has an invalid SHA-256 value")

    return manifest


def load_dataset(
    dataset_path: Path, manifest_path: Path
) -> Tuple[List[dict], int, dict]:
    """Validate the dataset and return valid rows, skipped count, and manifest."""
    if not dataset_path.is_file():
        raise DatasetIntegrityError(f"Dataset asset is missing: {dataset_path}")
    if not manifest_path.is_file():
        raise DatasetIntegrityError(f"Dataset manifest is missing: {manifest_path}")

    manifest = _load_manifest(manifest_path)

    try:
        actual_hash = sha256_file(dataset_path)
    except OSError as exc:
        raise DatasetIntegrityError(f"Cannot read dataset asset: {dataset_path}") from exc
    if actual_hash.lower() != manifest["sha256"].lower():
        raise DatasetIntegrityError("Dataset SHA-256 does not match the manifest")

    try:
        lines = [
            line
            for line in dataset_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeError) as exc:
        raise DatasetIntegrityError(f"Cannot parse dataset asset: {dataset_path}") from exc

    if len(lines) != manifest["record_count"]:
        raise DatasetIntegrityError("Dataset physical record count does not match the manifest")

    rows: List[dict] = []
    skipped = 0
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(row, dict):
            skipped += 1
            continue
        rows.append(row)

    if not rows:
        raise DatasetIntegrityError("Dataset contains no valid records")

    return rows, skipped, manifest


def _parse_iso_date(value: object) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if value == parsed.isoformat() else None


def hard_filter_reason(
    profile: dict, opportunity: dict, today: date
) -> Optional[str]:
    graduation_year = profile.get("graduation_year")
    target_years = opportunity.get("target_graduation_years")
    if (
        isinstance(graduation_year, int)
        and isinstance(target_years, list)
        and target_years
        and graduation_year not in target_years
        and profile.get("allow_graduation_mismatch") is not True
    ):
        return "届别不符"

    requested_types = profile.get("recruitment_types")
    offered_types = opportunity.get("recruitment_types")
    if (
        isinstance(requested_types, list)
        and requested_types
        and isinstance(offered_types, list)
        and offered_types
        and not set(requested_types).intersection(offered_types)
    ):
        return "招聘类型不符"

    requested_cities = set(profile.get("preferred_cities") or [])
    requested_cities.update(profile.get("acceptable_cities") or [])
    opportunity_cities = opportunity.get("locations_normalized")
    if (
        profile.get("strict_city_match") is True
        and requested_cities
        and isinstance(opportunity_cities, list)
        and opportunity_cities
        and requested_cities.isdisjoint(opportunity_cities)
    ):
        return "城市不符"

    deadline = _parse_iso_date(opportunity.get("deadline_date"))
    if deadline is not None and deadline < today:
        return "已过期"
    return None


def classify_urgency(opportunity: dict, today: date) -> str:
    deadline_value = opportunity.get("deadline_date")
    deadline = _parse_iso_date(deadline_value)
    if deadline is not None:
        days_remaining = (deadline - today).days
        if 0 <= days_remaining <= 3:
            return "立即处理"
        if 4 <= days_remaining <= 7:
            return "本周处理"
        if days_remaining > 7:
            return "正常安排"
        return "疑似过期"
    if deadline_value is not None:
        return "疑似过期"

    updated_value = opportunity.get("updated_at")
    updated = _parse_iso_date(updated_value)
    if updated_value is not None and updated is None:
        return "疑似过期"
    if updated is None:
        return "截止未知"

    age = (today - updated).days
    if opportunity.get("deadline_raw") == "招满为止" and 0 <= age <= 7:
        return "立即处理"
    if age > 30:
        return "疑似过期"
    return "截止未知"


def tier_for_score(score: int) -> Optional[str]:
    if score >= 80:
        return "高度匹配"
    if score >= 65:
        return "值得投递"
    if score >= 50:
        return "保底或探索"
    return None


def _role_score(profile: dict, opportunity: dict, taxonomy: dict) -> Tuple[int, Optional[str]]:
    roles = opportunity.get("role_categories") or []
    preferred = profile.get("preferred_role_categories") or []
    acceptable = profile.get("acceptable_role_categories") or []
    for role in roles:
        if role in preferred:
            return 30, role
    for role in roles:
        if role in acceptable:
            return 18, role
    role_taxonomy = taxonomy.get("role_categories", {})
    for role in roles:
        adjacent = role_taxonomy.get(role, {}).get("adjacent_role_categories", [])
        if set(preferred).intersection(adjacent):
            return 18, role
    return 0, None


def _supported_skills(profile: dict) -> set:
    supported = set()
    for evidence in profile.get("resume_evidence") or []:
        if not isinstance(evidence, dict) or not str(evidence.get("text") or "").strip():
            continue
        supported.update(skill for skill in evidence.get("skills") or [] if isinstance(skill, str))
    return supported


def _evidence_score(profile: dict, matched_role: Optional[str], taxonomy: dict) -> int:
    if matched_role is None:
        return 0
    supported = _supported_skills(profile)
    role_taxonomy = taxonomy.get("role_categories", {})
    direct_skills = set(role_taxonomy.get(matched_role, {}).get("skills", []))
    direct_count = len(supported.intersection(direct_skills))
    if direct_count >= 2:
        return 25
    if direct_count == 1:
        return 15
    adjacent_skills = set()
    for adjacent in role_taxonomy.get(matched_role, {}).get("adjacent_role_categories", []):
        adjacent_skills.update(role_taxonomy.get(adjacent, {}).get("skills", []))
    return 8 if supported.intersection(adjacent_skills) else 0


def _city_score(profile: dict, opportunity: dict) -> Tuple[int, Optional[str]]:
    cities = opportunity.get("locations_normalized") or []
    for city in cities:
        if city in (profile.get("preferred_cities") or []):
            return 15, city
    for city in cities:
        if city in (profile.get("acceptable_cities") or []):
            return 10, city
    return 0, None


def _major_group(major: object, taxonomy: dict) -> Optional[str]:
    if not isinstance(major, str):
        return None
    for group, majors in taxonomy.get("major_groups", {}).items():
        if major in majors:
            return group
    return None


def _major_score(profile: dict, matched_role: Optional[str], taxonomy: dict) -> int:
    group = _major_group(profile.get("major"), taxonomy)
    if group is None or matched_role is None:
        return 0
    role_taxonomy = taxonomy.get("role_categories", {})
    role_info = role_taxonomy.get(matched_role, {})
    if group in role_info.get("direct_major_groups", []):
        return 15
    for adjacent in role_info.get("adjacent_role_categories", []):
        if group in role_taxonomy.get(adjacent, {}).get("direct_major_groups", []):
            return 8
    return 0


def _company_score(profile: dict, opportunity: dict) -> int:
    companies = profile.get("preferred_companies") or []
    industries = profile.get("preferred_industries") or []
    if not companies and not industries:
        return 5
    if opportunity.get("company") in companies:
        return 10
    if set(industries).intersection(opportunity.get("company_categories") or []):
        return 10
    return 0


def _conditions_score(profile: dict, opportunity: dict) -> int:
    years = opportunity.get("target_graduation_years") or []
    recruitment_types = opportunity.get("recruitment_types") or []
    written_test = opportunity.get("written_test")
    if years and profile.get("graduation_year") not in years:
        return 0
    requested = profile.get("recruitment_types") or []
    if requested and recruitment_types and not set(requested).intersection(recruitment_types):
        return 0
    if profile.get("written_test_preference") == "avoid" and written_test is True:
        return 0
    if not years or not recruitment_types or written_test is None:
        return 3
    return 5


def score_opportunity(profile: dict, opportunity: dict, taxonomy: dict) -> dict:
    role, matched_role = _role_score(profile, opportunity, taxonomy)
    evidence = _evidence_score(profile, matched_role, taxonomy)
    city, matched_city = _city_score(profile, opportunity)
    major = _major_score(profile, matched_role, taxonomy)
    company = _company_score(profile, opportunity)
    conditions = _conditions_score(profile, opportunity)
    breakdown = {
        "role": role,
        "evidence": evidence,
        "city": city,
        "major": major,
        "company": company,
        "conditions": conditions,
    }
    total = sum(breakdown.values())
    reasons = []
    if matched_role:
        reasons.append(f"岗位方向匹配：{matched_role}")
    if matched_city:
        reasons.append(f"城市匹配：{matched_city}")
    if evidence:
        reasons.append(f"简历证据支持能力匹配：{evidence} 分")
    if major:
        reasons.append(f"专业 {profile.get('major')} 与岗位分类相关")
    if company:
        reasons.append(f"企业或行业偏好匹配：{company} 分")

    gaps = []
    if not opportunity.get("target_graduation_years"):
        gaps.append("需要查看公告确认目标毕业届别")
    if not opportunity.get("recruitment_types"):
        gaps.append("需要查看公告确认招聘类型")
    if opportunity.get("written_test") is None:
        gaps.append("需要查看公告确认笔试要求")
    if opportunity.get("verification_required"):
        gaps.append("源数据标记为需要人工确认")
    if not opportunity.get("application_url"):
        gaps.append("需要人工确认投递链接")

    return {
        "opportunity": opportunity,
        "score": total,
        "tier": tier_for_score(total),
        "urgency": "截止未知",
        "matched_role_category": matched_role,
        "matched_city": matched_city,
        "score_breakdown": breakdown,
        "reasons": reasons,
        "gaps": gaps,
        "graduation_filter_relaxed": bool(profile.get("allow_graduation_mismatch")),
    }


def search(
    profile: dict,
    opportunities: List[dict],
    taxonomy: dict,
    today: date,
    limit: int = 15,
    include_expired: bool = False,
) -> List[dict]:
    results = []
    for opportunity in opportunities:
        rejection = hard_filter_reason(profile, opportunity, today)
        if rejection and not (include_expired and rejection == "已过期"):
            continue
        result = score_opportunity(profile, opportunity, taxonomy)
        if result["tier"] is None:
            continue
        result["urgency"] = classify_urgency(opportunity, today)
        results.append(result)

    urgency_rank = {"立即处理": 0, "本周处理": 1, "正常安排": 2, "截止未知": 3, "疑似过期": 4}

    def sort_key(result: dict) -> tuple:
        opportunity = result["opportunity"]
        updated = _parse_iso_date(opportunity.get("updated_at")) or date.min
        return (
            -result["score"],
            urgency_rank.get(result["urgency"], 5),
            -updated.toordinal(),
            str(opportunity.get("company") or ""),
            str(opportunity.get("opportunity_id") or ""),
        )

    results.sort(key=sort_key)
    return results[: max(0, min(limit, 15))]


def _read_json_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid {label} JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} JSON must be an object")
    return value


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search bundled campus opportunities")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--today", type=str, default=date.today().isoformat())
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--include-expired", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = _parse_args(argv)
        profile = _read_json_object(args.profile, "profile")
        graduation_year = profile.get("graduation_year")
        if not isinstance(graduation_year, int) or isinstance(graduation_year, bool):
            raise ValueError("profile.graduation_year must be an integer")
        taxonomy = _read_json_object(args.taxonomy, "taxonomy")
        try:
            today = date.fromisoformat(args.today)
        except ValueError as exc:
            raise ValueError("--today must use YYYY-MM-DD") from exc
        opportunities, skipped, manifest = load_dataset(args.dataset, args.manifest)
        recommendations = search(
            profile,
            opportunities,
            taxonomy,
            today,
            limit=args.limit,
            include_expired=args.include_expired,
        )
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_version": manifest.get("dataset_version", "unknown"),
            "valid_records": len(opportunities),
            "skipped_records": skipped,
            "recommendations": recommendations,
        }
        print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
        return 0
    except (DatasetIntegrityError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
