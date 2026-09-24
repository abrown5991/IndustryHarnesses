"""Harness configuration: model tiers and runtime settings.

Model IDs are Bedrock inference-profile / model IDs and are configurable via
environment variables. The defaults below are placeholders — VERIFY the exact
Bedrock model IDs available in your account/region (e.g. via the AWS MCP or
`aws bedrock list-inference-profiles`) before deploying.
"""

import os

# AWS region the agent runs in.
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")

# Primary model: complex reasoning (defect root-cause, line-balancing analysis,
# multi-station correlation).
# TODO(verify): confirm exact Bedrock model/inference-profile ID for your region.
PRIMARY_MODEL_ID = os.getenv(
    "PRIMARY_MODEL_ID",
    "us.anthropic.claude-opus-4-8-v1:0",
)

# Fast/cheap model tier: routine lookups, part queries, and summaries.
# TODO(verify): confirm exact Bedrock model/inference-profile ID for your region.
FAST_MODEL_ID = os.getenv(
    "FAST_MODEL_ID",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
)

# Sampling / generation controls. Plant ops favors low temperature for
# deterministic, auditable answers.
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

# --- Complexity-based model routing -------------------------------------------
# When enabled, each request is scored for complexity and routed to the FAST or
# PRIMARY model tier (see router.py). Disable to always use PRIMARY.
ROUTING_ENABLED = os.getenv("ROUTING_ENABLED", "true").lower() == "true"

# Heuristic score thresholds: score <= LOW -> fast, score >= HIGH -> primary,
# in-between -> ambiguous band.
ROUTING_LOW_THRESHOLD = float(os.getenv("ROUTING_LOW_THRESHOLD", "0.35"))
ROUTING_HIGH_THRESHOLD = float(os.getenv("ROUTING_HIGH_THRESHOLD", "0.6"))

# For the ambiguous band, optionally ask the FAST model to classify the prompt
# as SIMPLE/COMPLEX. Costs one cheap call; off by default (ambiguous -> primary).
ROUTING_USE_LLM_FALLBACK = (
    os.getenv("ROUTING_USE_LLM_FALLBACK", "false").lower() == "true"
)

# Safety-sensitive prompts force-route to PRIMARY regardless of complexity.
ROUTING_ESCALATE_SAFETY = (
    os.getenv("ROUTING_ESCALATE_SAFETY", "true").lower() == "true"
)

# --- Bedrock Knowledge Base (RAG) ---------------------------------------------
KB_ID = os.getenv("KB_ID", "")
KB_RESULTS_COUNT = int(os.getenv("KB_RESULTS_COUNT", "5"))
KB_S3_BUCKET = os.getenv("KB_S3_BUCKET", "automotive-mfg-harness-kb-docs")
