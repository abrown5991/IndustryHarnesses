"""Automotive Plant-Ops harness — AgentCore Runtime entrypoint.

Implements the AgentCore Runtime service contract:
  - POST /invocations : agent interaction
  - GET  /ping        : health check
  - listens on 0.0.0.0:8080

The agent bundles: a plant-ops system prompt, a primary Claude model on Bedrock,
and a set of plant tools (currently mock stand-ins for real MCP servers).
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel

import config
from plant_tools import PLANT_TOOLS
from rag_tool import retrieve_knowledge_base
from router import ModelRouter

app = FastAPI(title="Automotive Plant-Ops Harness", version="0.1.0")

_SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "plant_ops_system.md").read_text()


def _build_agent(model_id: str) -> Agent:
    return Agent(
        model=BedrockModel(
            model_id=model_id,
            region_name=config.AWS_REGION,
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS,
        ),
        system_prompt=_SYSTEM_PROMPT,
        tools=[*PLANT_TOOLS, retrieve_knowledge_base],
    )


# One agent per tier, built once and reused across requests.
_agents = {
    "fast": _build_agent(config.FAST_MODEL_ID),
    "primary": _build_agent(config.PRIMARY_MODEL_ID),
}


def _classify_with_fast_model(prompt: str) -> str:
    """Ask the FAST model to label a prompt SIMPLE or COMPLEX (router fallback)."""
    classifier = Agent(
        model=BedrockModel(
            model_id=config.FAST_MODEL_ID,
            region_name=config.AWS_REGION,
            temperature=0.0,
            max_tokens=8,
        ),
        system_prompt=(
            "Classify the user's request by the reasoning effort it needs. "
            "Reply with exactly one word: SIMPLE (a lookup or single fact) or "
            "COMPLEX (multi-step reasoning, analysis, or synthesis)."
        ),
    )
    return str(classifier(prompt).message)


_router = ModelRouter(
    fast_model_id=config.FAST_MODEL_ID,
    primary_model_id=config.PRIMARY_MODEL_ID,
    low_threshold=config.ROUTING_LOW_THRESHOLD,
    high_threshold=config.ROUTING_HIGH_THRESHOLD,
    llm_classifier=_classify_with_fast_model,
    use_llm_fallback=config.ROUTING_USE_LLM_FALLBACK,
    escalate_safety=config.ROUTING_ESCALATE_SAFETY,
)


class InvocationRequest(BaseModel):
    input: Dict[str, Any]


class InvocationResponse(BaseModel):
    output: Dict[str, Any]


@app.post("/invocations", response_model=InvocationResponse)
async def invoke_agent(request: InvocationRequest):
    prompt = request.input.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="Invalid input: 'prompt' must be a non-empty string",
        )
    # Route to a model tier by complexity (or force PRIMARY if routing is off).
    if config.ROUTING_ENABLED:
        decision = _router.route(prompt)
        routing_meta = {
            "tier": decision.tier,
            "model_id": decision.model_id,
            "reason": decision.reason,
            "method": decision.method,
            "score": decision.score,
        }
        agent = _agents[decision.tier]
    else:
        routing_meta = {
            "tier": "primary",
            "model_id": config.PRIMARY_MODEL_ID,
            "reason": "routing disabled",
            "method": "disabled",
            "score": None,
        }
        agent = _agents["primary"]

    try:
        result = agent(prompt)
        return InvocationResponse(
            output={
                "message": result.message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "routing": routing_meta,
            }
        )
    except Exception as e:  # noqa: BLE001 — surface failure to caller
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {e}")


@app.get("/ping")
async def ping():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
