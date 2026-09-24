# Life-Sciences Harness — Research Scientists

An industry-specific agent **harness** for life-sciences R&D scientists,
packaged as a single container and deployable to **Amazon Bedrock AgentCore
Runtime**. Same architecture as the Energy and Automotive harnesses — only
the tools, prompt, and MCP registry change.

A "harness" bundles four layers into one deployable unit:

| Layer | This repo |
|-------|-----------|
| **Model** | Claude (primary + fast tier) on Amazon Bedrock — see `config.py` |
| **Tools / MCPs** | Research data sources — currently **mock** stand-ins in `research_tools.py`; real MCP servers registered in `mcp_config.json` |
| **Context** | Research system prompt: scientific rigor, no fabrication, ALCOA+ data integrity, biosecurity guardrails — `prompts/research_system.md` |
| **App** | FastAPI server implementing the AgentCore contract — `agent.py` |

## What the harness serves

- **Persona:** bench and computational scientists in drug discovery,
  molecular biology, genomics, biochemistry
- **Tasks:** literature synthesis, gene/variant/pathway lookup, small-molecule
  and target queries, protein-structure retrieval, LIMS assay interpretation,
  clinical-trial landscape, experimental-design critique, ELN drafting

## MCPs the scientist persona needs

| MCP server | What it provides | Real-world backend |
|---|---|---|
| `pubmed` | Literature citations and abstracts | PubMed / Europe PMC |
| `ncbi-gene` | Gene / variant / pathway lookup | NCBI Gene, Ensembl, UniProt |
| `chembl` | Small-molecule bioactivity, targets, IC50/Ki | ChEMBL, PubChem |
| `pdb-alphafold` | Experimental and predicted protein structures | RCSB PDB, AlphaFold DB |
| `lims` | Assay / screening / omics results | Benchling, Genedata, in-house LIMS |
| `clinicaltrials` | Clinical-trial landscape | ClinicalTrials.gov, WHO ICTRP |
| `eln` | Draft ELN entries (scientist signs) | Benchling, LabArchives |

Public data sources (PubMed, PDB, ChEMBL, AlphaFold DB, ClinicalTrials.gov) have
mature APIs but few production MCP wrappers today — usually you'll build a
thin MCP shim over each. Internal LIMS/ELN integrations are custom. This repo
uses **mocks in `research_tools.py`** so the harness runs end-to-end today.

## AgentCore Runtime contract

The container must satisfy this contract (all handled by `agent.py` + `Dockerfile`):

- Platform **`linux/arm64`**
- Listen on **port 8080**
- **`POST /invocations`** — agent interaction
- **`GET /ping`** — health check
- Image stored in **Amazon ECR**

## Files

```
life-sciences-harness/
├── agent.py                     # FastAPI app: /invocations + /ping, wires model+tools
├── config.py                    # Model IDs + generation settings (env-overridable)
├── research_tools.py            # MOCK tools (literature, gene, compounds, structure, LIMS, trials, ELN)
├── mcp_config.json              # Placeholder registry of real MCP servers to plug in
├── prompts/
│   └── research_system.md       # System prompt / rigor + integrity guardrails
├── Dockerfile                   # ARM64 container per AgentCore contract
├── deploy.sh                    # One-shot build + push + IAM + create_agent_runtime
├── deploy_agent.py              # create_agent_runtime from the ECR image
├── invoke_agent.py              # invoke_agent_runtime helper
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
  -d '{"input":{"prompt":"Summarize the KRAS G12C inhibitor resistance literature."}}'
```

Local runs need AWS credentials with `bedrock:InvokeModel` for the model to respond.

## Deploy to AgentCore (one command)

```bash
ACCOUNT=<your-account-id> REGION=us-west-2 ./deploy.sh
# then:
RUNTIME_ARN=<arn-printed-by-deploy> uv run invoke_agent.py "Draft an ELN entry for..."
```

## Going from mock to production

1. Stand up (or point at) each MCP server in `mcp_config.json` — start with
   the public-data ones (PubMed, ChEMBL, PDB) since APIs are stable.
2. Replace each mock in `research_tools.py` with a Strands `MCPClient` that
   calls the real server's tools.
3. **Verify model IDs** in `config.py` against your region
   (`aws bedrock list-inference-profiles`).
4. **Tighten IAM**: `iam/execution-role-permissions.json` uses `Resource: "*"`
   for speed of setup — scope Bedrock to specific model ARNs and logs to the
   runtime's log group before any production use.
5. Enable **AgentCore Observability** (CloudWatch Transaction Search) for tracing.
6. If the harness will touch **regulated (GxP) systems** or **patient-identifiable
   data**, add QA sign-off, audit logging, and PHI/PII controls before wiring.

## Safety notes

- **No fabrication.** The system prompt forbids invented citations,
  accession numbers, or assay values. Verify the model actually cites tool
  output before trusting a fact.
- **ELN entries are drafts.** `create_eln_entry` never signs or commits —
  the scientist reviews and signs per ALCOA+ / 21 CFR Part 11.
- **Biosecurity.** The prompt forbids guidance that could enable dangerous
  pathogens or toxins. Log and review these interactions.
- **Not clinical advice.** This is a research aid, not a diagnostic tool.
