# Multiple AI Agent for Business-Plan Generation withGenerative AI

This repository implements a research-oriented system for generating structured business proposals with cloud-hosted large language models (LLMs) and configurable small language model (SLM) runtimes. The product scope contains executed LLM pathways **A** and **B**, together with the complete SLM integration and preserved engineering evidence for planned condition **D**. Condition D reached real-model preflight but failed its feasibility gate; it was not executed as a formal, scored experiment.

The system separates generative reasoning from deterministic controls. Pydantic schemas define intermediate and final artifacts; bounded request and token budgets constrain model calls; evidence and financial checks identify unsupported content; and run records preserve the state required for inspection and recovery. The repository contains product source code, tests, evaluation instrumentation, the governing metric specification, and the frozen plans and execution records for the two completed A/B cases. Unrelated debugging archives, model weights, credentials, and local virtual environments are excluded.

## Research and engineering objectives

The project has four objectives:

1. implement comparable single-agent and multi-agent proposal-generation pathways;
2. preserve evidence provenance, uncertainty, and financial assumptions across generation stages;
3. provide deterministic validation, bounded correction, persistent run records, and separate audit artifacts; and
4. support both hosted LLMs and resource-constrained SLM deployments through a shared application architecture.

The repository is intended for controlled experimentation, system development, and reproducible evaluation. Generated proposals require domain review before they are used for investment, legal, regulatory, or operational decisions.

## Executed pathways and condition D status

The experimental description in this repository is limited to the two pathways that were executed.

| Pathway | Architecture | Model | Execution path |
| --- | --- | --- | --- |
| **A** | Single Agent | Gemini 2.5 Flash | A single model produces a structured proposal from the product brief. Schema validation, bounded correction, terminal checks, and separate audit generation are applied around the model response. |
| **B** | Multi-Agent | Gemini 2.5 Flash | A controlled graph executes input validation, deterministic supervision, Research, Strategy, Finance, retrieval, batched writing, final Critic review, conditional revision, and export. |
| **D (preflight only)** | Reviewed Multi-Agent | IBM Granite 4.0 H Micro, CPU/32K | Real-model preflight was attempted and preserved. Warmup and context checks passed, but four component outputs hit their frozen output caps on both the initial and sole structure-repair calls. The complete D smoke and formal D slots were therefore not run. |

Both pathways use explicit budgets and structured output contracts. Their implementations differ in orchestration, prompts, schemas, retrieval, and intermediate artifacts. The comparison should therefore be interpreted as a product-level comparison between two complete execution pathways, rather than as an isolated estimate of the effect of agent count.

## System architecture

### Pathway A: Single Agent

```text
Product brief
    -> single proposal generator
    -> schema and content validation
    -> bounded correction when required
    -> formal proposal and separate audit record
```

Pathway A is implemented through the baseline proposal route in `app.py`. It is designed for direct generation with limited orchestration and a compact execution trace.

### Pathway B: Multi-Agent

```text
Product brief
    -> Validator
    -> deterministic Supervisor
    -> Research
    -> Strategy
    -> Finance
    -> Web and local RAG retrieval
    -> batched Writer
    -> final Critic
    -> conditional Revision
    -> Export
```

Pathway B uses an explicit LangGraph workflow. Specialist outputs are validated before they enter downstream prompts. The Writer assembles the proposal in bounded batches, while the Critic and Revision stages operate under the same run-level accounting and persistence controls.

### SLM runtime

The `slm/` package provides an isolated runtime for small language models. It supports baseline, deterministic-workflow, and multi-agent execution through the same shared schemas and persistence layer used by the LLM application. The current local configuration targets IBM Granite 4.0 H Micro through an Ollama-compatible endpoint with an explicit 32,768-token context configuration.

The SLM layer includes:

- OpenAI-compatible client adapters;
- structured-output and schema-pruning controls;
- context-window and endpoint preflight checks;
- request, token, and wall-clock limits;
- owned-process and endpoint-lease management;
- Windows memory and awake-state monitoring;
- compact protocol and best-effort execution modes; and
- CLI entry points for baseline, workflow, and multi-agent runs.

SLM behavior depends on the selected model, quantization, endpoint implementation, available memory, and context configuration. Deployment-specific claims should be supported by measurements from the target environment.

### Experiment D evidence boundary

The restored D materials are indexed at `experiments/product_d_slm/README.md`. They contain plans, frozen inputs, code snapshots, preflight attempts, raw model responses, resource samples, validation logs, and a separately labelled best-effort demo.

The authoritative D preflight outcome is `no_go`, not a successful formal result. The final preserved preflight used 10 requests, 30,817 tokens, and 1,233.531 active seconds cumulatively. Its complete smoke was not run, both formal D slots remained unexecuted, and the C-D comparison is unavailable. The best-effort 13-section artifact is explicitly non-formal and is not eligible to substitute for condition D.

## Repository structure

| Path | Purpose |
| --- | --- |
| `app.py` | Streamlit application and product entry points |
| `agents/` | Research, Strategy, Finance, Writer, Supervisor, and Critic components |
| `workflow/` | Single-agent, deterministic, multi-agent, validation, review, budget, and export logic |
| `schemas/` | Pydantic contracts for proposals, evidence, finance, reviews, and workflow state |
| `rag/` | Local indexing, retrieval, evidence filtering, and citation checks |
| `tools/` | Web-search integration, source-quality rules, and recency handling |
| `storage/` | SQLAlchemy models, repositories, and run persistence |
| `prompts/` | Versioned prompts for the proposal and specialist roles |
| `knowledge_base/` | General proposal templates and business-analysis frameworks |
| `slm/` | SLM clients, adapters, preflight checks, Granite configuration, and CLI |
| `tests/` | LLM workflow, product-contract, storage, RAG, and reliability tests |
| `slm/tests/` | SLM isolation, adapter, preflight, process, and resource-control tests |
| `evaluation/` | Metric computation, resource sampling, audit, export, and statistical utilities |
| `tools/run_product_ab.py` | Frozen A/B execution harness with request, event, timing, token, cost, and code-identity recording |
| `tools/summarize_product_ab.py` | Deterministic reduction of A/B execution records into metric artifacts |
| `docs/evaluation/` | Versioned evaluation specification used to interpret captured records |
| `docs/final_sprint/` | Restored A-D protocol, SLM/D preflight history, raw evidence, validation, and final no-go records |
| `experiments/product_ab/` | A/B plans, audits, manifests, raw calls, node records, checkpoints, and derived metrics |
| `experiments/product_d_slm/` | Audit and navigation index for the restored SLM/condition-D evidence chain |

## Requirements

- Python 3.12
- Gemini API credentials for pathways A and B
- Tavily credentials when live Web retrieval is enabled for pathway B
- an OpenAI-compatible SLM endpoint for SLM execution
- Ollama when using the supplied local Granite configuration

Model weights and local Ollama data are not stored in this repository.

## Installation

Create an isolated Python environment and install the shared and SLM dependencies:

```powershell
python -m venv .venv
& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r slm\requirements-slm.txt
```

Create the LLM configuration file from the supplied template:

```powershell
Copy-Item .env.example .env
```

Set at least the following variables in `.env`:

```dotenv
GEMINI_API_KEY=<your-key>
TAVILY_API_KEY=<your-key>
DEFAULT_MODEL=gemini-2.5-flash
```

Do not commit `.env`, `slm/.env.slm`, API credentials, generated outputs, local databases, endpoint leases, or model files.

## Running the LLM application

Start the Streamlit interface from the repository root:

```powershell
python -m streamlit run app.py
```

Within the application, use the **Baseline** route for pathway A and the **Multi-Agent** route for pathway B. The deterministic **Workflow** route is an auxiliary staged pipeline and is not an additional experimental arm in the A/B scope documented here.

Generated Markdown files are written to `outputs/`. Run metadata, node outputs, errors, source records, and token usage are persisted through the storage layer.

## Configuring an SLM endpoint

Create an SLM environment file:

```powershell
Copy-Item slm\.env.slm.example slm\.env.slm
```

For a local Ollama deployment of Granite 4.0 H Micro, create the configured model alias:

```powershell
ollama create granite-h-micro-32k -f slm\Modelfile.granite-h-micro-32k
```

Configure `slm/.env.slm` for the local OpenAI-compatible endpoint:

```dotenv
SLM_BASE_URL=http://127.0.0.1:11434/v1
SLM_MODEL_NAME=granite-h-micro-32k
SLM_API_KEY=ollama
SLM_CONTEXT_PROBE=1
```

The context probe should remain enabled unless the endpoint's effective context limit has been independently verified. A server-side context window smaller than the configured prompt and output budget can silently remove instructions from the beginning of a request.

Run an included example through the SLM CLI:

```powershell
python -m slm.cli --mode baseline --input slm\examples\ai_education.json
python -m slm.cli --mode workflow --input slm\examples\ai_education.json
python -m slm.cli --mode multi --input slm\examples\ai_education.json
```

Each command performs preflight checks before dispatching model requests. The multi-agent mode also requires the local knowledge base and any configured retrieval services.

## Validation

The following focused test set checks imports, LLM client behavior, the multi-agent graph, and the principal SLM interfaces without invoking live model services:

```powershell
python -m pytest -q `
  tests\test_workflow_imports.py `
  tests\test_llm_client.py `
  tests\test_multi_agent_graph.py `
  slm\tests\test_slm_client.py `
  slm\tests\test_slm_pipeline.py
```

Tests marked `live` require external credentials or a running model endpoint and should be executed deliberately in an authorized environment.

## Evaluation materials

The repository includes the [evaluation metric specification](docs/evaluation/@ai_agent_evaluation_metrics_spec_v2_fast_generation.md), the executable instrumentation and reduction modules, a structured [index of the completed A/B experimental materials](experiments/product_ab/README.md), and an [audit index for the restored D/SLM materials](experiments/product_d_slm/README.md). The D package preserves a real failed preflight and a non-formal best-effort demo; neither is presented as a completed formal observation.

The A/B harness records frozen inputs, execution order, model and budget settings, source-code hashes, append-only events, provider calls, token and cost accounting, node outputs, checkpoints, and terminal artifacts. The broader `evaluation/` package contains resource sampling and formal metric-reduction utilities required by the evaluation protocol. Experimental interpretation remains outside the scope of this product README.

## Reproducibility and audit boundaries

The product runtime records workflow versions, prompt versions, model usage, intermediate node outputs, source metadata, and terminal status where the selected path supports them. Formal proposal text and audit information are stored separately so that internal validation metadata does not become part of the user-facing document.

The frozen A/B packages preserve the inputs, source-code hashes, model configuration, execution order, request accounting, raw provider records, and derived metrics used for research traceability. The D package preserves its failed preflight, exact no-go rationale, raw calls, resource observations, cleanup evidence, and formal non-eligibility decision. Intermediate or superseded records are retained where necessary to preserve the execution history; the artifact indexes identify the authoritative presentation copies. Reproducing every metric additionally requires the environment and resource conditions specified by the evaluation protocol.

## Security and data handling

- Keep credentials in ignored local environment files or a managed secret store.
- Review persisted source text and generated proposals before sharing them.
- Do not add SQLite databases, endpoint leases, credentials, or confidential user material. The frozen A/B packages intentionally retain the reviewed raw provider records required for experimental traceability.
- Treat external Web content and retrieved documents as untrusted input.
- Apply human review to financial, legal, regulatory, and market claims.
