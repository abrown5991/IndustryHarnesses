# AgentCore Runtime requires linux/arm64.
FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
RUN uv sync --no-cache || true
COPY uv.lock* ./
RUN uv sync --no-cache

# Copy application code.
COPY config.py router.py rag_tool.py research_tools.py agent.py ./
COPY prompts ./prompts

# AgentCore Runtime contract: listen on 8080.
EXPOSE 8080

CMD ["uv", "run", "uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8080"]
