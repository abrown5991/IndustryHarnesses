"""Amazon Bedrock Knowledge Base retrieval tool.

Wraps the Bedrock managed Knowledge Base (RAG) as a Strands tool. The KB ID
and result count come from config (env-overridable at runtime) so the same
container image works for any KB — no rebuild needed when the KB is updated.

Industry-specific content lives in S3 and is indexed by the KB. Each harness
points this tool at its own KB via KB_ID in config.py / env vars.

This file is identical across all harnesses — only the KB_ID (and the S3
documents it indexes) differ.
"""

from __future__ import annotations

from typing import Any, Dict, List

import boto3
from strands import tool

import config

_client: Any = None


def _kb_client():
    """Lazy singleton — avoids cold-start boto3 init on import."""
    global _client
    if _client is None:
        _client = boto3.client("bedrock-agent-runtime", region_name=config.AWS_REGION)
    return _client


@tool
def retrieve_knowledge_base(query: str) -> Dict[str, Any]:
    """Search the industry knowledge base for relevant documents and procedures.

    Use this tool when a question may be addressed by internal documentation:
    operating procedures, standards, guidelines, SOPs, technical manuals, or
    domain-specific reference material stored in the knowledge base.

    Always prefer grounding answers in retrieved KB content over general
    knowledge. Cite the S3 document URI and relevance score in your answer.

    Args:
        query: The search query — phrase it as a question or keyword set that
               captures what you need to find, e.g.
               "NERC CIP-014 physical security requirements" or
               "KRAS G12C dose-response protocol SOP".

    Returns retrieved passages with their source document URIs and scores.
    If the KB ID is not configured (KB_ID env var), returns an instructional
    note rather than failing, so the agent can continue without RAG.
    """
    kb_id = config.KB_ID
    if not kb_id:
        return {
            "source": "knowledge-base",
            "status": "NOT_CONFIGURED",
            "note": (
                "KB_ID is not set. Set KB_ID env var to the Bedrock Knowledge Base ID "
                "to enable retrieval. Run setup_kb.py to provision the knowledge base."
            ),
            "results": [],
        }

    try:
        response = _kb_client().retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": config.KB_RESULTS_COUNT}
            },
        )
    except Exception as e:  # noqa: BLE001
        return {
            "source": "knowledge-base",
            "status": "ERROR",
            "error": str(e),
            "results": [],
        }

    results: List[Dict[str, Any]] = []
    for r in response.get("retrievalResults", []):
        uri = (
            r.get("location", {})
            .get("s3Location", {})
            .get("uri", "unknown")
        )
        results.append(
            {
                "text": r.get("content", {}).get("text", ""),
                "source_uri": uri,
                "score": round(r.get("score", 0.0), 4),
            }
        )

    return {
        "source": "bedrock-knowledge-base",
        "kb_id": kb_id,
        "query": query,
        "results": results,
        "result_count": len(results),
    }
