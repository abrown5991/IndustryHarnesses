# Energy Harness — Grid / Utility Operations

An industry-specific agent **harness** for electric-utility control-room
operations, packaged as a container and deployable to **Amazon Bedrock
AgentCore Runtime**.

A "harness" here bundles four layers into one deployable unit:

| Layer | This repo |
|-------|-----------|
| **Model** | Claude (primary + fast tier) on Amazon Bedrock — see `config.py` |
| **Tools / MCPs** | Grid data sources — currently **mock** stand-ins in `grid_tools.py`; real MCP servers registered in `mcp_config.json` |
| **Context** | Grid-ops system prompt with NERC/CIP & safety guardrails — `prompts/grid_ops_system.md` |
| **App** | FastAPI server implementing the AgentCore contract — `agent.py` |

## AgentCore Runtime contract

The container must satisfy this contract (all handled by `agent.py` + `Dockerfile`):

- Platform **`linux/arm64`**
- Listen on **port 8080**
- **`POST /invocations`** — agent interaction
- **`GET /ping`** — health check
- Image stored in **Amazon ECR**

## Files

```
energy-grid-harness/
├── agent.py                 # FastAPI app: /invocations + /ping, wires model+tools
├── config.py                # Model IDs + generation settings (env-overridable)
├── grid_tools.py            # MOCK grid tools (SCADA, OMS, ISO, forecast, weather, work-order)
├── mcp_config.json          # Placeholder registry of real MCP servers to plug in
├── prompts/
│   └── grid_ops_system.md   # System prompt / domain guardrails
├── Dockerfile               # ARM64 container per AgentCore contract
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
  -d '{"input":{"prompt":"Summarize grid status for NORTH-3 and any active outages."}}'
```

Local runs need AWS credentials with `bedrock:InvokeModel` for the model to respond.

## Deploy to AgentCore

Set your account/region first. **ARM64 is required.**

```bash
ACCOUNT=<your-account-id>
REGION=us-west-2
REPO=energy-grid-harness

# 1. ECR repo + login
aws ecr create-repository --repository-name $REPO --region $REGION
aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com

# 2. Build for ARM64 and push
docker buildx create --use   # once
docker buildx build --platform linux/arm64 \
  -t $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest --push .

# 3. Create the IAM execution role (trust + permissions in iam/)
aws iam create-role --role-name EnergyGridHarnessRuntimeRole \
  --assume-role-policy-document file://iam/execution-role-trust-policy.json
aws iam put-role-policy --role-name EnergyGridHarnessRuntimeRole \
  --policy-name EnergyGridHarnessRuntimePermissions \
  --policy-document file://iam/execution-role-permissions.json

# 4. Create the runtime
CONTAINER_URI=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest \
EXECUTION_ROLE_ARN=arn:aws:iam::$ACCOUNT:role/EnergyGridHarnessRuntimeRole \
  uv run deploy_agent.py

# 5. Invoke (use the ARN printed by step 4)
RUNTIME_ARN=<arn-from-step-4> \
  uv run invoke_agent.py "What's the 12-hour load forecast for NORTH-3?"
```

## Going from mock to production

1. Stand up (or point at) each MCP server in `mcp_config.json`.
2. Replace each mock in `grid_tools.py` with a Strands `MCPClient` that calls
   the real server's tools.
3. **Verify model IDs** in `config.py` against your region
   (`aws bedrock list-inference-profiles`).
4. **Tighten IAM**: `iam/execution-role-permissions.json` uses `Resource: "*"`
   for speed of setup — scope Bedrock to specific model ARNs and logs to the
   runtime's log group before any production use.
5. Enable **AgentCore Observability** (CloudWatch Transaction Search) for
   tracing.

## Safety note

This is decision-support tooling for a safety-critical system. The harness is
designed to **read before write**: `create_work_order` only drafts orders for
human approval, and the system prompt forbids autonomous control actions. Keep
that posture when wiring real SCADA/EMS integrations.
