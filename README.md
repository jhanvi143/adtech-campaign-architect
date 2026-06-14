# Adtech Campaign Architect 🚀

A local ad-campaign planner that turns an advertiser one-liner into a ranked publisher recommendation, persona reasoning, ad creative variants, and a structured campaign config with budget, bid, CPA, and cost guardrails.

This is a basic prototype I built in a day. The goal was to show the end-to-end idea working locally: understand an advertiser query, retrieve relevant publishers/personas, and generate a campaign draft. It is not production grade yet.

## Run It ⚙️

Requires Python 3.10+ and Ollama. I use Ollama so the prototype can run against open-source/local models without paid API usage. The default model is `qwen3.5:0.8b`, a deliberately small model so inference is faster and the demo can run on ordinary laptops for now.

Install Ollama first 🦙:

```bash
# macOS or Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# Download from https://ollama.com/download or use:
powershell -Command "irm https://ollama.com/install.ps1 | iex"
```

Then run the app:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python3 scripts/run_pipeline.py
```

Open `http://127.0.0.1:8000`. The first run can take a few minutes because the script starts Ollama if needed and downloads `qwen3.5:0.8b` if it is not already present. After that, the model is cached locally and startup/inference is faster.

Use another local model or port with:

```bash
python3 scripts/run_pipeline.py --model qwen3.5:0.8b --fallback-model qwen3.5:0.8b --port 8001
```

Run one sample advertiser and print JSON:

```bash
python3 scripts/run_pipeline.py --example 1
```

Docker option:

```bash
docker compose up --build
```

Docker runs the app plus `ollama/ollama`. First startup still downloads the model into the Docker volume.

CLI option:

```bash
PYTHONPATH=src OLLAMA_MODEL=qwen3.5:0.8b python3 -m adtech_campaign_architect.cli "We sell premium dog food for senior dogs, targeting owners who care about joint health and longevity."
```

The app has deterministic fallbacks, so basic demos and tests still run if Ollama is unavailable. For semantic retrieval, install the optional dependencies in `requirements.txt`; without them, retrieval falls back to deterministic scoring.

## How It Works 🧠

`build_campaign()` in `src/adtech_campaign_architect/planner.py` runs the campaign pipeline:

1. Query understanding 🔎: Ollama/Qwen reads the advertiser brief and extracts the product, category, subcategory, attributes, audience, price sensitivity, motivations, disinterests, and expected AOV. Low-signal inputs return clarifying questions instead of forcing a campaign.
2. Retrieval 📚: those extracted terms are used to retrieve the best publisher and persona candidates. When LlamaIndex/Hugging Face embeddings are installed, this uses semantic search over the publisher/persona catalog; otherwise it uses deterministic category, audience, AOV, and positioning scores.
3. Candidate selection 🎯: the LLM reviews the top retrieved publishers/personas and chooses the primary publisher/persona pair, with reasoning and a click hypothesis.
4. Campaign generation ✍️: the LLM builds persona-specific creative variants plus a campaign configuration for the selected publisher and ranked publisher set. The config includes target personas, budget allocation, bid type/range, target CPA guardrail, expected cost logic, and financial reasoning.

The current implementation generates two creative variations to keep local latency low on the small model. Expanding this to three to five variants is straightforward: broaden the persona candidate set, increase the creative call limit, and keep the same normalization path.

## Why Ollama 💸

Ollama keeps the prototype local, inspectable, and cheap to run. That tradeoff is useful for a take-home because anyone can run the same code without provisioning API keys or spending on hosted inference. The small model is not the final production choice; it is a pragmatic default that favors portability and speed over maximum reasoning quality.

## UI Note 🎨

The UI is only meant to make the prototype visual and easy to inspect. It is not intended to be the final product screen. A real product UI could be improved quite a lot with proper workflows, editable campaign fields, better review states, explainability, QA surfaces, and launch/approval controls.

## What I Cut ✂️

I did not add persistence, paid LLM APIs, image creatives, account auth, live ad-platform integrations, or a full evaluation harness. The prototype is intentionally local and easy to inspect.

## What Is Hard 🧩

The hardest part was figuring out what prompts to write so the LLM could build useful campaign creative instead of generic ad copy. The prompt has to give the model enough context about the advertiser, persona, publisher, bid strategy, and cost logic while still forcing a structured output that the UI can trust.

The other hard part was selecting the correct publisher from a short advertiser query. Semantic similarity alone is not enough: a wellness product, pet-health product, and vague "feel better" product can look close in embedding space, but only one may be launchable on a given publisher. The retrieval and LLM selection steps work together so the system can extract terms from the query, find candidate publishers, and then reason over fit instead of blindly trusting score rank.

## Production Path 🏗️

To make this production grade, I would add a proper vector database instead of an in-memory prototype index, build more rigorous prompts for query understanding, add strong guardrails for malformed inputs and risky claims, and use the right domain expertise to tune publisher/persona matching, bid strategy, and campaign constraints.

I would also add labeled evals for every sample advertiser, cache embeddings, add model-output validation with retry/repair prompts, expose editable campaign fields in the UI, generate three to five creative variations by default, and add policy checks for health, sustainability, and performance claims.

For deployment, the next infrastructure step would be moving from Ollama to vLLM and a far more optimized inference pipeline. vLLM would let the same generation path serve many more requests through continuous batching, better GPU utilization, and much higher throughput once the model choice, prompts, and guardrails are stable.
