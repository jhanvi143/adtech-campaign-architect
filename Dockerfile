FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    OLLAMA_URL=http://ollama:11434 \
    OLLAMA_MODEL=qwen3.5:0.8b \
    OLLAMA_FALLBACK_MODEL=qwen3.5:0.8b \
    OLLAMA_KEEP_ALIVE=30m

COPY pyproject.toml requirements.txt ./
COPY src ./src
COPY prompts ./prompts
COPY scripts ./scripts
COPY data ./data
COPY README.md GLOSSARY.md ./

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "-m", "adtech_campaign_architect.run_pipeline", "--port", "8000"]
