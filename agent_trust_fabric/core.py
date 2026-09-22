"""Deterministic authority checks and tamper-evident local receipts.

This is a reference evaluator. Input identities, timestamps, and approvals are
assertions from the caller; production trust requires authenticated transport,
trusted clocks, externally verified signatures, and a durable evidence store.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from typing import Any


SUPPORTED_SOURCES = {"generic", "langgraph", "crewai", "paperclip"}
REQUIRED = {"event_id", "run_id", "agent_id", "source", "time", "action", "resource", "authority"}
RESOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_./:-]+$")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be ISO 8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def validate_event(event: dict[str, Any]) -> None:
    if not isinstance(event, dict) or REQUIRED - event.keys():
        raise ValueError(f"event missing required fields: {sorted(REQUIRED - event.keys()) if isinstance(event, dict) else sorted(REQUIRED)}")
    for key in ("event_id", "run_id", "agent_id", "action", "resource"):
        if not isinstance(event[key], str) or not event[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    if not isinstance(event["source"], str) or event["source"] not in SUPPORTED_SOURCES:
        raise ValueError("unsupported source")
    resource = event["resource"]
    if (
        not RESOURCE_PATTERN.fullmatch(resource)
        or any(part in {"", ".", ".."} for part in resource.split("/"))
        or "\\" in resource
    ):
        raise ValueError("resource must be a canonical slash-delimited identifier")
    timestamp(event["time"])
    authority = event["authority"]
    if not isinstance(authority, dict) or not isinstance(authority.get("actions"), list):
        raise ValueError("authority.actions must be an array")
    if any(not isinstance(action, str) or not action for action in authority["actions"]):
        raise ValueError("authority.actions must contain nonempty strings")
    if not isinstance(authority.get("resource_prefix"), str) or not authority["resource_prefix"]:
        raise ValueError("authority.resource_prefix must be a nonempty string")
    prefix = authority["resource_prefix"]
    if (
        not RESOURCE_PATTERN.fullmatch(prefix)
        or not prefix.endswith("/")
        or any(part in {"", ".", ".."} for part in prefix[:-1].split("/"))
    ):
        raise ValueError("authority.resource_prefix must be a canonical directory prefix ending in /")
    timestamp(authority.get("expires_at"))
    if "amount" in event and (type(event["amount"]) not in (int, float) or not math.isfinite(event["amount"]) or event["amount"] < 0):
        raise ValueError("amount must be nonnegative")
    if "cost_usd" in event and (type(event["cost_usd"]) not in (int, float) or not math.isfinite(event["cost_usd"]) or event["cost_usd"] < 0):
        raise ValueError("cost_usd must be nonnegative")
    if "max_amount" in authority and (type(authority["max_amount"]) not in (int, float) or not math.isfinite(authority["max_amount"]) or authority["max_amount"] < 0):
        raise ValueError("authority.max_amount must be nonnegative")
    try:
        canonical(event)
    except (TypeError, ValueError) as exc:
        raise ValueError("event must contain only finite JSON values") from exc


def decide(event: dict[str, Any], used_approvals: set[str]) -> tuple[str, list[str]]:
    """Return an explicit allow/deny decision; never authorize from absent data."""
    validate_event(event)
    authority = event["authority"]
    when = timestamp(event["time"])
    reasons: list[str] = []
    if event["action"] not in authority["actions"]:
        reasons.append("ACTION_OUT_OF_SCOPE")
    if not event["resource"].startswith(authority["resource_prefix"]):
        reasons.append("RESOURCE_OUT_OF_SCOPE")
    if when >= timestamp(authority["expires_at"]):
        reasons.append("AUTHORITY_EXPIRED")
    if authority.get("agent_id") != event["agent_id"]:
        reasons.append("AGENT_MISMATCH")
    if authority.get("run_id") != event["run_id"]:
        reasons.append("RUN_MISMATCH")
    amount = event.get("amount")
    max_amount = authority.get("max_amount")
    if amount is not None and (type(max_amount) not in (int, float) or amount > max_amount):
        reasons.append("AMOUNT_OUT_OF_SCOPE")
    if event["action"] in {"refund.issue", "access.grant", "physical.act"}:
        approval = event.get("approval")
        if not isinstance(approval, dict) or not isinstance(approval.get("id"), str) or not approval["id"]:
            reasons.append("APPROVAL_MISSING")
        else:
            if approval["id"] in used_approvals:
                reasons.append("APPROVAL_REPLAY")
            if approval.get("agent_id") != event["agent_id"]:
                reasons.append("APPROVAL_AGENT_MISMATCH")
            if approval.get("action") != event["action"] or approval.get("run_id") != event["run_id"]:
                reasons.append("APPROVAL_SCOPE_MISMATCH")
            if approval.get("resource") != event["resource"]:
                reasons.append("APPROVAL_RESOURCE_MISMATCH")
            if approval.get("amount") != amount:
                reasons.append("APPROVAL_AMOUNT_MISMATCH")
            try:
                if when >= timestamp(approval.get("expires_at")):
                    reasons.append("APPROVAL_EXPIRED")
            except ValueError:
                reasons.append("APPROVAL_INVALID_EXPIRY")
    return ("deny", reasons) if reasons else ("allow", ["AUTHORIZED"])


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(case, dict) or not isinstance(case.get("events"), list):
        raise ValueError("case.events must be an array")
    if not case["events"]:
        raise ValueError("case.events must not be empty")
    receipts: list[dict[str, Any]] = []
    used_approvals: set[str] = set()
    event_ids: set[str] = set()
    previous = "0" * 64
    for event in case["events"]:
        validate_event(event)
        if event["event_id"] in event_ids:
            raise ValueError("duplicate event_id")
        event_ids.add(event["event_id"])
        decision, reasons = decide(event, used_approvals)
        if decision == "allow" and event.get("approval"):
            used_approvals.add(event["approval"]["id"])
        body = {
            "sequence": len(receipts) + 1,
            "event_id": event["event_id"],
            "run_id": event["run_id"],
            "agent_id": event["agent_id"],
            "source": event["source"],
            "time": event["time"],
            "action": event["action"],
            "resource": event["resource"],
            "decision": decision,
            "reasons": reasons,
            "input_sha256": digest(event),
            "cost_usd": event.get("cost_usd", 0),
            "previous_sha256": previous,
        }
        receipt = {**body, "sha256": digest(body)}
        previous = receipt["sha256"]
        receipts.append(receipt)
    return {
        "schema_version": "0.1.0",
        "case_id": case.get("case_id", "unnamed"),
        "receipts": receipts,
        "chain_tip_sha256": previous,
        "passport": {
            "events": len(receipts),
            "allowed": sum(r["decision"] == "allow" for r in receipts),
            "denied": sum(r["decision"] == "deny" for r in receipts),
            "total_reported_cost_usd": round(sum(r["cost_usd"] for r in receipts), 6),
            "frameworks": sorted({r["source"] for r in receipts}),
            "authority_basis": "caller_asserted_reference_fixture",
            "evidence_status": "INTEGRITY_ONLY_NOT_AUTHENTICATED",
        },
    }


def verify(bundle: dict[str, Any], case: dict[str, Any] | None = None) -> list[str]:
    """Check local chain integrity; optionally compare receipts to original inputs."""
    errors: list[str] = []
    receipts = bundle.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        return ["receipts missing"]
    previous = "0" * 64
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, dict):
            errors.append(f"receipt {index + 1}: invalid object")
            continue
        body = {key: value for key, value in receipt.items() if key != "sha256"}
        if receipt.get("sequence") != index + 1:
            errors.append(f"receipt {index + 1}: sequence mismatch")
        if receipt.get("previous_sha256") != previous:
            errors.append(f"receipt {index + 1}: broken chain")
        if receipt.get("sha256") != digest(body):
            errors.append(f"receipt {index + 1}: digest mismatch")
        previous = receipt.get("sha256", "")
        if case is not None:
            try:
                if receipt.get("input_sha256") != digest(case["events"][index]):
                    errors.append(f"receipt {index + 1}: input mismatch")
            except (IndexError, KeyError, TypeError):
                errors.append(f"receipt {index + 1}: input missing")
    if bundle.get("chain_tip_sha256") != previous:
        errors.append("chain tip mismatch")
    if case is not None:
        if len(case.get("events", [])) != len(receipts):
            errors.append("event count mismatch")
        else:
            try:
                expected = run_case(case)
                if expected["receipts"] != receipts or expected["passport"] != bundle.get("passport"):
                    errors.append("decision or passport mismatch")
            except ValueError as exc:
                errors.append(f"invalid original case: {exc}")
    return errors
