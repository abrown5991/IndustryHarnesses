#!/usr/bin/env bash
# One-command build + deploy of the Energy Grid-Ops harness to AgentCore Runtime.
#
# Bundles every step into a single container image and deploys it:
#   1. ECR repo (create if missing)
#   2. ARM64 buildx build + push
#   3. IAM execution role (create/update trust + permissions)
#   4. create_agent_runtime
#
# Usage:
#   ACCOUNT=123456789012 REGION=us-west-2 ./deploy.sh
#
# Optional env: REPO, RUNTIME_NAME, ROLE_NAME.
set -euo pipefail

: "${ACCOUNT:?set ACCOUNT to your AWS account id}"
REGION="${REGION:-us-west-2}"
REPO="${REPO:-energy-grid-harness}"
RUNTIME_NAME="${RUNTIME_NAME:-energy_grid_harness}"
ROLE_NAME="${ROLE_NAME:-EnergyGridHarnessRuntimeRole}"
IMAGE="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${REPO}:latest"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo ">> [1/4] Ensuring ECR repo '${REPO}' exists in ${REGION}"
aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO" --region "$REGION" >/dev/null
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

echo ">> [2/4] Building ARM64 image and pushing to ${IMAGE}"
docker buildx inspect harness-builder >/dev/null 2>&1 || docker buildx create --name harness-builder --use
docker buildx use harness-builder
docker buildx build --platform linux/arm64 -t "$IMAGE" --push "$HERE"

echo ">> [3/4] Ensuring IAM execution role '${ROLE_NAME}'"
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document "file://${HERE}/iam/execution-role-trust-policy.json" >/dev/null
fi
aws iam put-role-policy --role-name "$ROLE_NAME" \
  --policy-name EnergyGridHarnessRuntimePermissions \
  --policy-document "file://${HERE}/iam/execution-role-permissions.json"
ROLE_ARN="arn:aws:iam::${ACCOUNT}:role/${ROLE_NAME}"

echo ">> [4/5] Provisioning Bedrock Knowledge Base"
KB_ID="${KB_ID:-}"
if [ -z "$KB_ID" ]; then
  KB_ID="$(ACCOUNT="$ACCOUNT" uv run "${HERE}/setup_kb.py" 2>&1 \
    | grep "^   KB_ID=" | cut -d= -f2)"
  echo "  KB_ID=${KB_ID}"
else
  echo "  Using existing KB_ID=${KB_ID}"
fi

echo ">> [5/5] Creating AgentCore runtime '${RUNTIME_NAME}'"
CONTAINER_URI="$IMAGE" EXECUTION_ROLE_ARN="$ROLE_ARN" \
  AWS_REGION="$REGION" RUNTIME_NAME="$RUNTIME_NAME" KB_ID="$KB_ID" \
  uv run "${HERE}/deploy_agent.py"

echo ">> Done. Invoke with: RUNTIME_ARN=<arn-above> uv run invoke_agent.py \"...\""
echo ">> Upload KB docs: aws s3 cp <file> s3://energy-grid-harness-kb-docs/"
echo ">> Re-sync KB: ACCOUNT=$ACCOUNT KB_ID=$KB_ID uv run setup_kb.py --sync-only"
