"""Invoke the deployed Life-Sciences Research harness.

Usage:
  RUNTIME_ARN=arn:aws:bedrock-agentcore:us-west-2:<acct>:runtime/<name>-<suffix> \
  uv run invoke_agent.py "Summarize recent literature on KRAS G12C resistance."
"""

import json
import os
import sys
import uuid

import boto3

REGION = os.environ.get("AWS_REGION", "us-west-2")
RUNTIME_ARN = os.environ["RUNTIME_ARN"]

prompt = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "Summarize the current landscape of KRAS G12C inhibitor resistance."
)

client = boto3.client("bedrock-agentcore", region_name=REGION)

response = client.invoke_agent_runtime(
    agentRuntimeArn=RUNTIME_ARN,
    runtimeSessionId=uuid.uuid4().hex + uuid.uuid4().hex,  # must be 33+ chars
    payload=json.dumps({"input": {"prompt": prompt}}),
    qualifier="DEFAULT",
)

print(json.loads(response["response"].read()))
