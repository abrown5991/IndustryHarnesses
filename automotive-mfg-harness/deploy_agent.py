"""Create (or update) the AgentCore Runtime from the pushed container image.

Prerequisites:
  - Image built for linux/arm64 and pushed to ECR (see README).
  - An IAM execution role (see iam/) whose ARN is passed below.

Usage:
  CONTAINER_URI=<acct>.dkr.ecr.us-west-2.amazonaws.com/automotive-mfg-harness:latest \
  EXECUTION_ROLE_ARN=arn:aws:iam::<acct>:role/AutomotiveMfgHarnessRuntimeRole \
  uv run deploy_agent.py
"""

import os

import boto3

REGION = os.environ.get("AWS_REGION", "us-west-2")
CONTAINER_URI = os.environ["CONTAINER_URI"]
EXECUTION_ROLE_ARN = os.environ["EXECUTION_ROLE_ARN"]
RUNTIME_NAME = os.environ.get("RUNTIME_NAME", "automotive_mfg_harness")

client = boto3.client("bedrock-agentcore-control", region_name=REGION)

response = client.create_agent_runtime(
    agentRuntimeName=RUNTIME_NAME,
    agentRuntimeArtifact={
        "containerConfiguration": {"containerUri": CONTAINER_URI}
    },
    networkConfiguration={"networkMode": "PUBLIC"},
    roleArn=EXECUTION_ROLE_ARN,
    lifecycleConfiguration={
        "idleRuntimeSessionTimeout": 300,   # 5 min
        "maxLifetime": 1800,                # 30 min
    },
)

print("Agent Runtime created.")
print("ARN:   ", response["agentRuntimeArn"])
print("Status:", response["status"])
