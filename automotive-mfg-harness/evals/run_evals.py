"""Eval runner for the automotive plant-ops harness.

Layers:
  A. routing        — deterministic, no model call. Always runs.
  B. tool-use + behavior — runs the agent (needs Bedrock), rule-based grading.
  C. quality        — LLM-as-judge against evals/rubric.md (needs Bedrock).

Usage:
  uv run evals/run_evals.py --offline    # Layer A only, no AWS
  uv run evals/run_evals.py              # A + B
  uv run evals/run_evals.py --judge      # A + B + C

Exit code is non-zero if any case fails.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_HARNESS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HARNESS_DIR))

import config  # noqa: E402
from router import ModelRouter  # noqa: E402
from graders import (  # noqa: E402
    CaseReport,
    grade_behavior,
    grade_quality,
    grade_routing,
    grade_tool_use,
)

DATASET = Path(__file__).parent / "dataset.jsonl"
RUBRIC = Path(__file__).parent / "rubric.md"


def load_cases(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _text_of(message: Any) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        content = message.get("content", [])
        if isinstance(content, list):
            return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
        return str(content)
    return str(message)


def _tools_called(agent: Any) -> List[str]:
    names: List[str] = []
    for msg in getattr(agent, "messages", []) or []:
        for block in (msg.get("content", []) if isinstance(msg, dict) else []):
            if isinstance(block, dict) and "toolUse" in block:
                name = block["toolUse"].get("name")
                if name:
                    names.append(name)
    return names


def run(offline: bool, judge: bool) -> int:
    cases = load_cases(DATASET)
    router = ModelRouter(
        fast_model_id=config.FAST_MODEL_ID,
        primary_model_id=config.PRIMARY_MODEL_ID,
        low_threshold=config.ROUTING_LOW_THRESHOLD,
        high_threshold=config.ROUTING_HIGH_THRESHOLD,
        escalate_safety=config.ROUTING_ESCALATE_SAFETY,
    )

    agent_mod = None
    rubric_text = ""
    if not offline:
        import agent as agent_mod  # noqa: F401
        if judge:
            rubric_text = RUBRIC.read_text()

    reports: List[CaseReport] = []
    for case in cases:
        report = CaseReport(case_id=case["id"])
        report.grades.append(grade_routing(case, router))

        if not offline:
            tier = router.route(case["prompt"]).tier
            agent = agent_mod._agents[tier]
            result = agent(case["prompt"])
            text = _text_of(result.message)
            report.grades.append(grade_tool_use(case, _tools_called(agent)))
            report.grades.extend(grade_behavior(case, text))
            if judge:
                def judge_fn(p: str) -> str:
                    return _text_of(agent_mod._agents["primary"](p).message)
                report.grades.append(grade_quality(case, text, rubric_text, judge_fn))

        reports.append(report)

    return _print_report(reports, offline, judge)


def _print_report(reports: List[CaseReport], offline: bool, judge: bool) -> int:
    layers = "A(routing)" + ("" if offline else " + B(tool+behavior)") + (
        " + C(quality)" if (judge and not offline) else ""
    )
    print(f"\n=== Automotive Plant-Ops Harness Evals — layers: {layers} ===\n")
    n_pass = 0
    for r in reports:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.case_id}")
        for g in r.grades:
            print(f"  {'✓' if g.passed else '✗'} {g.name}: {g.detail}")
        n_pass += 1 if r.passed else 0
    print(f"\n{n_pass}/{len(reports)} cases passed.\n")
    return 0 if n_pass == len(reports) else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Run automotive plant-ops harness evals.")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--judge", action="store_true")
    args = ap.parse_args()
    sys.exit(run(offline=args.offline, judge=args.judge))


if __name__ == "__main__":
    main()
