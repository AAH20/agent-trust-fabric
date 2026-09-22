"""Offline demo and verification CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import run_case, verify
from .report import render_html, render_markdown
from .simulation import simulate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-trust")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("run", help="Evaluate a synthetic or exported case")
    demo.add_argument("case", type=Path)
    demo.add_argument("--output", type=Path)
    demo.add_argument("--format", choices=("json", "markdown", "html"), default="json")
    check = sub.add_parser("verify", help="Verify a receipt bundle and original case")
    check.add_argument("bundle", type=Path)
    check.add_argument("--case", type=Path, required=True)
    bench = sub.add_parser("benchmark", help="Check declared expected decisions against the reference policy")
    bench.add_argument("case", type=Path)
    scenario = sub.add_parser("simulate", help="Run a paired, reproducible synthetic scenario experiment")
    scenario.add_argument("scenario", type=Path)
    scenario.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "simulate":
            result = simulate(json.loads(args.scenario.read_text(encoding="utf-8")))
            output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
            if args.output:
                args.output.write_text(output, encoding="utf-8")
            else:
                sys.stdout.write(output)
            return 0
        if args.command == "run":
            result = run_case(json.loads(args.case.read_text(encoding="utf-8")))
            if args.format == "markdown":
                output = render_markdown(result)
            elif args.format == "html":
                output = render_html(result)
            else:
                output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
            if args.output:
                args.output.write_text(output, encoding="utf-8")
            else:
                sys.stdout.write(output)
            return 0
        if args.command == "benchmark":
            case = json.loads(args.case.read_text(encoding="utf-8"))
            expected = case.get("expected_decisions")
            if not isinstance(expected, list) or len(expected) != len(case.get("events", [])):
                raise ValueError("expected_decisions must match the events array")
            observed = [receipt["decision"] for receipt in run_case(case)["receipts"]]
            for index, (want, got) in enumerate(zip(expected, observed), start=1):
                print(f"{index}: expected={want} observed={got}")
            if observed != expected:
                print("benchmark failed", file=sys.stderr)
                return 1
            print("benchmark passed: synthetic fixture only")
            return 0
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        case = json.loads(args.case.read_text(encoding="utf-8"))
        errors = verify(bundle, case)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("verified: local integrity and deterministic replay match; producer authenticity unproven")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
