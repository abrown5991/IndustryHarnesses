# Industry Harnesses

Industry-specific AI agent harnesses deployable to **Amazon Bedrock AgentCore Runtime**.

Each harness is a self-contained ARM64 container that bundles:
- **Model routing** — complexity + safety-based routing between Claude Opus (primary) and Haiku (fast)
- **Domain tools** — mock MCP integrations (swappable for real servers via `mcp_config.json`)
- **Bedrock Knowledge Base (RAG)** — S3-backed retrieval of internal documentation
- **System prompt** — industry-specific guardrails, personas, and domain context
- **Evaluations** — 3-layer eval suite (routing / tool+behavior / LLM-judge quality)

## Harnesses

| Directory | Industry | Persona | Key tools |
|---|---|---|---|
| [`energy-grid-harness/`](energy-grid-harness/) | Energy | Grid/utility operators | SCADA, OMS, ISO market, load forecast, weather, work orders |
| [`automotive-mfg-harness/`](automotive-mfg-harness/) | Automotive | Plant/manufacturing engineers | MES/OEE, PLC historian, quality/defects, predictive maintenance, ERP/JIT, CMMS |
| [`life-sciences-harness/`](life-sciences-harness/) | Life Sciences | R&D scientists | PubMed, gene/compound/structure DBs, LIMS, ClinicalTrials, ELN |

## Deploy (any harness)

```bash
cd <harness-directory>
ACCOUNT=<aws-account-id> REGION=us-west-2 ./deploy.sh
```

`deploy.sh` runs 5 steps: ECR → ARM64 image build+push → IAM role → Bedrock Knowledge Base → AgentCore runtime.

## Local test

```bash
cd <harness-directory>
uv sync
uv run uvicorn agent:app --host 0.0.0.0 --port 8080
curl -X POST localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{"input":{"prompt":"<your question>"}}'
```

## Evals

```bash
cd <harness-directory>
uv run evals/run_evals.py --offline   # routing only, no AWS (CI gate)
uv run evals/run_evals.py             # + tool-use & behavior (needs Bedrock)
uv run evals/run_evals.py --judge     # + LLM quality judge (release gate)
```

## Architecture

```
agent.py          FastAPI /invocations + /ping (AgentCore contract)
config.py         Model IDs, routing thresholds, KB config (all env-overridable)
router.py         Complexity + safety-based model routing (shared across harnesses)
rag_tool.py       Bedrock Knowledge Base retrieval tool (shared)
*_tools.py        Domain tool mocks (swap for real MCP clients)
mcp_config.json   Real MCP server registry (plug in when ready)
prompts/          Industry-specific system prompt + guardrails
evals/            dataset.jsonl, rubric.md, graders.py, run_evals.py
iam/              IAM trust + permissions for runtime and KB service roles
Dockerfile        linux/arm64 per AgentCore contract
deploy.sh         One-shot build + deploy script
setup_kb.py       Bedrock Knowledge Base + S3 provisioner
```

## AgentCore Runtime contract

- Platform: `linux/arm64`
- Port: `8080`
- `POST /invocations` — agent interaction
- `GET /ping` — health check
- Image in Amazon ECR

## Knowledge base documents

Upload industry-specific documents to the harness's S3 bucket, then re-sync:

```bash
aws s3 cp <document> s3://<harness>-kb-docs/
ACCOUNT=<id> KB_ID=<id> uv run setup_kb.py --sync-only
```

| Harness | S3 bucket | Suggested documents |
|---|---|---|
| Energy | `energy-grid-harness-kb-docs` | EOPs, switching procedures, NERC standards, relay settings |
| Automotive | `automotive-mfg-harness-kb-docs` | FMEAs, control plans, torque specs, IATF procedures, LOTO |
| Life Sciences | `life-sciences-harness-kb-docs` | SOPs, assay protocols, safety data sheets, study reports |
