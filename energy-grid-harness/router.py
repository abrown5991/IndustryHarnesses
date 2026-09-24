"""Complexity-based model router.

Routes each incoming question to the cheapest model that can answer it well:

  - FAST tier (e.g. Haiku): short lookups, definitions, single-fact queries.
  - PRIMARY tier (e.g. Opus): multi-step reasoning, analysis, synthesis,
    root-cause, design, cross-source correlation.

Two-stage decision, cheapest first:

  1. Heuristic pass — signal scoring on the prompt text. Zero extra latency or
     cost. Resolves the clear cases (obvious lookup vs. obviously complex).
  2. LLM fallback (optional) — for scores in the ambiguous middle band, ask the
     FAST model to classify SIMPLE vs COMPLEX. Costs one cheap call. Disabled by
     default; when disabled, ambiguous prompts route to PRIMARY (bias to quality).

This module is industry-agnostic — the same router ships in every harness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

# --- Signal vocabularies -------------------------------------------------------

# Verbs / phrases that signal genuine reasoning, analysis, or multi-step work.
_COMPLEX_MARKERS = (
    "analy",          # analyze, analysis
    "compare",
    "contrast",
    "synthes",        # synthesize, synthesis
    "root cause",
    "why ",
    " why?",
    "diagnos",
    "troubleshoot",
    "design",
    "evaluate",
    "assess",
    "trade-off",
    "tradeoff",
    "correlate",
    "hypothes",
    "implication",
    "recommend",
    "optimi",         # optimize, optimization
    "explain how",
    "explain why",
    "step by step",
    "step-by-step",
    "walk me through",
    "pros and cons",
    "what if",
    "should i",
    "plan for",
    "strategy",
    "prioriti",
)

# Safety-sensitive markers. When escalation is on, any hit forces the PRIMARY
# (most capable) model regardless of complexity, so refusals and high-stakes
# boundary decisions get the strongest model. Superset across harness domains
# (biosecurity, clinical, and physical-control safety).
_SAFETY_MARKERS = (
    # biosecurity / dual-use
    "pathogen", "toxin", "bioweapon", "gain of function", "gain-of-function",
    "select agent", "virulence", "transmissibility", "weaponi",
    # clinical boundary (individual patient care)
    "my patient", "prescribe", "what dose", "dosage for", "diagnose my",
    "treat my", "should i take",
    # data-integrity / regulated-record actions (ELN finalization, 21 CFR Part 11)
    "finalize", "finalise", "commit the", "sign the", "sign off",
    # physical / control-system safety (grid, plant)
    # Single-word terms that are almost always safety-critical in these domains.
    "interlock",          # "override the interlock", "defeat interlock", etc.
    "lockout",            # LOTO
    "tagout",             # LOTO
    "setpoint",           # PLC/control-system parameter changes
    "protection relay",   # grid protection equipment
    "thermal limit",      # running above thermal limits
    "bypass", "disable safety", "disable the safety",
    "disable protection", "override protection",
    # general hazard
    "explosive", "make a weapon", "how to make a bomb",
)

# Phrases that signal a simple lookup / single fact / short answer.
_SIMPLE_MARKERS = (
    "what is",
    "what's",
    "define",
    "definition of",
    "look up",
    "lookup",
    "list ",
    "get ",
    "fetch ",
    "find the",
    "status of",
    "how many",
    "when is",
    "when was",
    "who is",
    "where is",
    "show me",
)


@dataclass
class RoutingDecision:
    """Result of a routing call."""

    tier: str          # "fast" | "primary"
    model_id: str
    reason: str
    method: str        # "heuristic" | "llm" | "default"
    score: float       # complexity score in [0, 1] (heuristic estimate)


class ModelRouter:
    """Chooses FAST vs PRIMARY model for a given prompt by complexity."""

    def __init__(
        self,
        fast_model_id: str,
        primary_model_id: str,
        *,
        low_threshold: float = 0.35,
        high_threshold: float = 0.6,
        llm_classifier: Optional[Callable[[str], str]] = None,
        use_llm_fallback: bool = False,
        escalate_safety: bool = True,
    ) -> None:
        """
        Args:
            fast_model_id: Model id for the FAST tier.
            primary_model_id: Model id for the PRIMARY tier.
            low_threshold: score <= this routes to FAST.
            high_threshold: score >= this routes to PRIMARY.
            llm_classifier: Optional fn(prompt) -> "SIMPLE"|"COMPLEX" used only
                for scores between the thresholds.
            use_llm_fallback: Enable the LLM classifier for the ambiguous band.
            escalate_safety: If True, safety-sensitive prompts force PRIMARY.
        """
        self.fast_model_id = fast_model_id
        self.primary_model_id = primary_model_id
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self.llm_classifier = llm_classifier
        self.use_llm_fallback = use_llm_fallback
        self.escalate_safety = escalate_safety

    # -- Public API -------------------------------------------------------------

    def route(self, prompt: str) -> RoutingDecision:
        # Safety escalation takes precedence over complexity: high-stakes /
        # refusal-worthy prompts always get the most capable model.
        if self.escalate_safety:
            text = (prompt or "").lower()
            hit = next((m for m in _SAFETY_MARKERS if m in text), None)
            if hit:
                return RoutingDecision(
                    tier="primary",
                    model_id=self.primary_model_id,
                    reason=f"Safety-sensitive marker ('{hit}') — escalated to primary.",
                    method="safety",
                    score=1.0,
                )

        score, signals = self._complexity_score(prompt)

        if score >= self.high_threshold:
            return RoutingDecision(
                tier="primary",
                model_id=self.primary_model_id,
                reason=f"High complexity ({signals}).",
                method="heuristic",
                score=score,
            )
        if score <= self.low_threshold:
            return RoutingDecision(
                tier="fast",
                model_id=self.fast_model_id,
                reason=f"Low complexity ({signals}).",
                method="heuristic",
                score=score,
            )

        # Ambiguous middle band.
        if self.use_llm_fallback and self.llm_classifier is not None:
            try:
                verdict = self.llm_classifier(prompt).strip().upper()
            except Exception:  # noqa: BLE001 — classifier failure must not break routing
                verdict = ""
            if "SIMPLE" in verdict:
                return RoutingDecision(
                    tier="fast",
                    model_id=self.fast_model_id,
                    reason="Ambiguous; LLM classifier said SIMPLE.",
                    method="llm",
                    score=score,
                )
            if "COMPLEX" in verdict:
                return RoutingDecision(
                    tier="primary",
                    model_id=self.primary_model_id,
                    reason="Ambiguous; LLM classifier said COMPLEX.",
                    method="llm",
                    score=score,
                )

        # Default for ambiguous: bias to quality.
        return RoutingDecision(
            tier="primary",
            model_id=self.primary_model_id,
            reason="Ambiguous complexity; defaulting to primary for quality.",
            method="default",
            score=score,
        )

    # -- Heuristic scoring ------------------------------------------------------

    def _complexity_score(self, prompt: str) -> tuple[float, str]:
        """Return (score in [0,1], human-readable signal summary)."""
        text = (prompt or "").lower().strip()
        if not text:
            return 0.0, "empty prompt"

        words = re.findall(r"\b\w+\b", text)
        n_words = len(words)
        n_questions = text.count("?")
        n_complex = sum(1 for m in _COMPLEX_MARKERS if m in text)
        n_simple = sum(1 for m in _SIMPLE_MARKERS if m in text)
        # Conjunctions / enumerations suggest multi-part requests.
        n_conjunctions = len(re.findall(r"\b(and|then|also|plus|as well as)\b", text))
        has_numbered_list = bool(re.search(r"(^|\n)\s*\d+[.)]\s", prompt or ""))

        score = 0.0
        # Length: longer prompts trend more complex.
        if n_words > 80:
            score += 0.35
        elif n_words > 40:
            score += 0.22
        elif n_words > 20:
            score += 0.10
        # Reasoning markers dominate the signal: 2 strong markers already push
        # into the primary band, 3+ make it decisive.
        score += min(0.66, 0.22 * n_complex)
        # Multiple questions / multi-part.
        if n_questions >= 2:
            score += 0.15
        if n_conjunctions >= 2:
            score += 0.12
        elif n_conjunctions == 1:
            score += 0.05
        if has_numbered_list:
            score += 0.10
        # Simple-lookup markers pull the score down.
        score -= min(0.30, 0.15 * n_simple)
        # Very short prompts with no complex markers are almost always simple.
        if n_words <= 8 and n_complex == 0:
            score -= 0.15

        score = max(0.0, min(1.0, score))
        summary = (
            f"words={n_words}, complex={n_complex}, simple={n_simple}, "
            f"questions={n_questions}, conj={n_conjunctions}"
        )
        return score, summary
