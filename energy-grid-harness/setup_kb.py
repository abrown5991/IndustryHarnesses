"""Provision the Bedrock Knowledge Base and S3 data source for this harness.

Creates (idempotent):
  1. S3 bucket  (KB_S3_BUCKET from config)
  2. IAM KB service role  (reads S3, invokes embedding model)
  3. Bedrock Knowledge Base  (Amazon Titan Embed v2, managed OpenSearch)
  4. S3 data source attached to the KB
  5. Starts an ingestion job to index any documents already in the bucket

After running, export the printed KB_ID and set it as an env var when
deploying the container (or add it to your deployment env).

Usage:
  ACCOUNT=123456789012 REGION=us-west-2 uv run setup_kb.py

To upload documents before (or after) running this script:
  aws s3 cp my-sop.pdf s3://<KB_S3_BUCKET>/docs/

Then re-sync with:
  ACCOUNT=... KB_ID=<id> uv run setup_kb.py --sync-only
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import boto3
import botocore.exceptions

import config

ACCOUNT = __import__("os").environ.get("ACCOUNT", "")
REGION = config.AWS_REGION
BUCKET = config.KB_S3_BUCKET

# IAM role names — stable across re-runs for idempotency.
KB_ROLE_NAME = f"{BUCKET}-kb-role"
# KB and data source names.
KB_NAME = BUCKET  # one KB per harness
DS_NAME = f"{BUCKET}-s3-source"
# Embedding model ARN for Titan Embed v2.
EMBEDDING_MODEL_ARN = (
    f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0"
)


def _iam() -> boto3.client:
    return boto3.client("iam", region_name=REGION)


def _s3() -> boto3.client:
    return boto3.client("s3", region_name=REGION)


def _bedrock_agent() -> boto3.client:
    return boto3.client("bedrock-agent", region_name=REGION)


# ── 1. S3 bucket ──────────────────────────────────────────────────────────────

def ensure_bucket() -> None:
    s3 = _s3()
    try:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET)
        else:
            s3.create_bucket(
                Bucket=BUCKET,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        print(f"  Created S3 bucket: s3://{BUCKET}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"  S3 bucket already exists: s3://{BUCKET}")
    # Block all public access.
    s3.put_public_access_block(
        Bucket=BUCKET,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )


# ── 2. IAM KB service role ────────────────────────────────────────────────────

def ensure_kb_role() -> str:
    iam = _iam()
    trust = json.load(
        open(__import__("pathlib").Path(__file__).parent / "iam" / "kb-service-role-trust-policy.json")
    )
    perms = json.load(
        open(__import__("pathlib").Path(__file__).parent / "iam" / "kb-service-role-permissions.json")
    )
    try:
        role = iam.create_role(
            RoleName=KB_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description=f"Bedrock Knowledge Base service role for {KB_NAME}",
        )["Role"]
        print(f"  Created IAM role: {KB_ROLE_NAME}")
    except iam.exceptions.EntityAlreadyExistsException:
        role = iam.get_role(RoleName=KB_ROLE_NAME)["Role"]
        print(f"  IAM role already exists: {KB_ROLE_NAME}")
    iam.put_role_policy(
        RoleName=KB_ROLE_NAME,
        PolicyName=f"{KB_NAME}-kb-policy",
        PolicyDocument=json.dumps(perms),
    )
    # Bedrock needs a moment after role creation before it can assume it.
    time.sleep(10)
    return role["Arn"]


# ── 3. Knowledge Base ─────────────────────────────────────────────────────────

def ensure_kb(role_arn: str) -> str:
    ba = _bedrock_agent()
    # Check if a KB with this name already exists.
    paginator = ba.get_paginator("list_knowledge_bases")
    for page in paginator.paginate():
        for kb in page.get("knowledgeBaseSummaries", []):
            if kb["name"] == KB_NAME:
                kb_id = kb["knowledgeBaseId"]
                print(f"  Knowledge Base already exists: {kb_id} ({KB_NAME})")
                return kb_id

    response = ba.create_knowledge_base(
        name=KB_NAME,
        description=f"Knowledge base for {KB_NAME} harness",
        roleArn=role_arn,
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": EMBEDDING_MODEL_ARN,
            },
        },
        storageConfiguration={
            "type": "OPENSEARCH_SERVERLESS",
            "opensearchServerlessConfiguration": {
                "collectionArn": "",  # Bedrock creates and manages the collection
                "vectorIndexName": f"{KB_NAME}-index",
                "fieldMapping": {
                    "vectorField": "embedding",
                    "textField": "text",
                    "metadataField": "metadata",
                },
            },
        },
    )
    kb_id = response["knowledgeBase"]["knowledgeBaseId"]
    print(f"  Created Knowledge Base: {kb_id} ({KB_NAME})")
    # Wait for ACTIVE status.
    _wait_kb_active(ba, kb_id)
    return kb_id


def _wait_kb_active(ba, kb_id: str, timeout: int = 300) -> None:
    print("  Waiting for Knowledge Base to become ACTIVE", end="", flush=True)
    for _ in range(timeout // 10):
        status = ba.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]["status"]
        if status == "ACTIVE":
            print(" ✓")
            return
        if status == "FAILED":
            print(" FAILED")
            raise RuntimeError(f"Knowledge Base {kb_id} entered FAILED state.")
        print(".", end="", flush=True)
        time.sleep(10)
    raise TimeoutError("Knowledge Base did not become ACTIVE within timeout.")


# ── 4. S3 data source ─────────────────────────────────────────────────────────

def ensure_data_source(kb_id: str) -> str:
    ba = _bedrock_agent()
    # Check if data source already exists.
    for ds in ba.list_data_sources(knowledgeBaseId=kb_id).get("dataSourceSummaries", []):
        if ds["name"] == DS_NAME:
            ds_id = ds["dataSourceId"]
            print(f"  Data source already exists: {ds_id} ({DS_NAME})")
            return ds_id

    response = ba.create_data_source(
        knowledgeBaseId=kb_id,
        name=DS_NAME,
        description=f"S3 documents for {KB_NAME}",
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": {
                "bucketArn": f"arn:aws:s3:::{BUCKET}",
            },
        },
        vectorIngestionConfiguration={
            "chunkingConfiguration": {
                "chunkingStrategy": "FIXED_SIZE",
                "fixedSizeChunkingConfiguration": {
                    "maxTokens": 512,
                    "overlapPercentage": 20,
                },
            }
        },
    )
    ds_id = response["dataSource"]["dataSourceId"]
    print(f"  Created data source: {ds_id} ({DS_NAME})")
    return ds_id


# ── 5. Ingestion job ──────────────────────────────────────────────────────────

def start_ingestion(kb_id: str, ds_id: str) -> None:
    ba = _bedrock_agent()
    response = ba.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=ds_id,
    )
    job_id = response["ingestionJob"]["ingestionJobId"]
    print(f"  Started ingestion job: {job_id}")
    print("  (Ingestion runs asynchronously. Check status in the Bedrock console.)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Provision Bedrock Knowledge Base for this harness.")
    ap.add_argument("--sync-only", action="store_true",
                    help="Skip creation steps; just start a new ingestion job on the existing KB.")
    args = ap.parse_args()

    if not ACCOUNT:
        print("ERROR: set ACCOUNT env var to your AWS account ID.", file=sys.stderr)
        sys.exit(1)

    if args.sync_only:
        kb_id = __import__("os").environ.get("KB_ID", "")
        if not kb_id:
            print("ERROR: set KB_ID env var for --sync-only.", file=sys.stderr)
            sys.exit(1)
        ba = _bedrock_agent()
        ds_list = ba.list_data_sources(knowledgeBaseId=kb_id)["dataSourceSummaries"]
        if not ds_list:
            print("ERROR: no data sources found on KB.", file=sys.stderr)
            sys.exit(1)
        start_ingestion(kb_id, ds_list[0]["dataSourceId"])
        return

    print(f"\n>> Provisioning Knowledge Base for: {KB_NAME}  (region={REGION})\n")

    print("[1/4] S3 bucket")
    ensure_bucket()

    print("[2/4] IAM KB service role")
    role_arn = ensure_kb_role()

    print("[3/4] Knowledge Base")
    kb_id = ensure_kb(role_arn)

    print("[4/4] S3 data source + ingestion")
    ds_id = ensure_data_source(kb_id)
    start_ingestion(kb_id, ds_id)

    print(f"\n>> Done.\n")
    print(f"   KB_ID={kb_id}")
    print(f"\n   Set KB_ID={kb_id} in your container env or deploy script.")
    print(f"   Upload documents to s3://{BUCKET}/ then run:")
    print(f"   ACCOUNT={ACCOUNT} KB_ID={kb_id} uv run setup_kb.py --sync-only\n")


if __name__ == "__main__":
    main()
