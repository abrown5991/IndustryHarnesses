# Automotive Harness — Manufacturing / Plant Operations

An industry-specific agent **harness** for automotive plant operations,
packaged as a single container and deployable to **Amazon Bedrock AgentCore
Runtime**. Same architecture as the Energy/Grid-Ops harness — only the
tools, prompt, and MCP registry change.

A "harness" bundles four layers into one deployable unit:

| Layer | This repo |
|-------|-----------|
| **Model** | Claude (primary + fast tier) on Amazon Bedrock — see `config.py` |
| **Tools / MCPs** | Plant data sources — currently **mock** stand-ins in `plant_tools.py`; real MCP servers registered in `mcp_config.json` |
| **Context** | Plant-ops system prompt with safety (LOTO), traceability (IATF 16949), and read-before-write guardrails — `prompts/plant_ops_system.md` |
| **App** | FastAPI server implementing the AgentCore contract — `agent.py` |

## What the harness serves

- **Persona:** line engineers, production supervisors, quality engineers, maintenance planners
- **Tasks:** OEE analysis, defect / non-conformance triage, predictive-maintenance
  review, VIN traceability, JIT parts risk, work-order drafting

## MCPs the automotive-plant persona needs

| MCP server | What it provides | Real-world backend |
|---|---|---|
| `mes-oee` | OEE, production counts, shift performance | MES (Rockwell FactoryTalk, Siemens Opcenter, custom) |
| `plc-historian` | Station telemetry, cycle times, torque, andon | OPC UA / Ignition / OSIsoft PI |
| `quality-mgmt` | Defects, non-conformances, containment, VIN linkage | QMS (Plex, IQMS, custom) |
| `predictive-maint` | Vibration/temperature signals, health scores | AWS Monitron, IoT SiteWise, vendor platforms |
| `erp-jit` | Parts supply, line-side inventory, ETAs | SAP, Oracle |
| `mes-traceability` | Per-VIN genealogy, torque events, station history | MES traceability layer |
| `cmms` | Maintenance work orders (drafts, human-approved) | SAP PM, IBM Maximo |

Real turnkey MCP servers for these systems mostly don't exist as products
yet — expect to build or wrap each one. This repo uses **mocks in
`plant_tools.py`** so the harness runs end-to-end today; swap them one by one
as real MCPs come online.

## AgentCore Runtime contract

The container must satisfy this contract (all handled by `agent.py` + `Dockerfile`):

- Platform **`linux/arm64`**
- Listen on **port 8080**
- **`POST /invocations`** — agent interaction
- **`GET /ping`** — health check
- Image stored in **Amazon ECR**

## Files

```
automotive-mfg-harness/
├── agent.py                 # FastAPI app: /invocations + /ping, wires model+tools
├── config.py                # Model IDs + generation settings (env-overridable)
├── plant_tools.py           # MOCK plant tools (OEE, station, defects, PdM, ERP, VIN, CMMS)
├── mcp_config.json          # Placeholder registry of real MCP servers to plug in
├── prompts/
│   └── plant_ops_system.md  # System prompt / domain guardrails
├── Dockerfile               # ARM64 container per AgentCore contract
├── deploy.sh                # One-shot build + push + IAM + create_agent_runtime
├── deploy_agent.py          # create_agent_runtime from the ECR image
├── invoke_agent.py          # invoke_agent_runtime helper
└── iam/
    ├── execution-role-trust-policy.json
    └── execution-role-permissions.json
```

## Local test

```bash
uv sync
uv run uvicorn agent:app --host 0.0.0.0 --port 8080
# in another shell:
curl localhost:8080/ping
curl -X POST localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{"input":{"prompt":"Summarize OEE on BODY-2 this shift and the top defect trend."}}'
```

Local runs need AWS credentials with `bedrock:InvokeModel` for the model to respond.

## Deploy to AgentCore (one command)

```bash
ACCOUNT=<your-account-id> REGION=us-west-2 ./deploy.sh
# then:
RUNTIME_ARN=<arn-printed-by-deploy> uv run invoke_agent.py "What's the OEE on BODY-2?"
```

The script builds the ARM64 image, pushes to ECR, creates/updates the IAM
execution role, and registers the AgentCore runtime — idempotent, safe to
re-run.

## Going from mock to production

1. Stand up (or point at) each MCP server in `mcp_config.json`.
2. Replace each mock in `plant_tools.py` with a Strands `MCPClient` that calls
   the real server's tools.
3. **Verify model IDs** in `config.py` against your region
   (`aws bedrock list-inference-profiles`).
4. **Tighten IAM**: `iam/execution-role-permissions.json` uses `Resource: "*"`
   for speed of setup — scope Bedrock to specific model ARNs and logs to the
   runtime's log group before any production use.
5. Enable **AgentCore Observability** (CloudWatch Transaction Search) for tracing.

## Safety note

Plant floors are safety-critical: robotics, presses, hazmat. The harness is
designed to **read before write**: `create_work_order` only drafts orders for
planner approval, and the system prompt forbids autonomous control of PLCs or
robots. Keep that posture when wiring real MES/PLC/CMMS integrations.
