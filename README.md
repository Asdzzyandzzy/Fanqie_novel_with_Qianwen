# Fanqie Short Story Pipeline with Local Qwen

This repository is a local LLM writing pipeline for structured Chinese short-story generation. It started as a practical experiment: how can a local Qwen model be guided to produce a complete Fanqie-style short story with stronger continuity, clearer pacing, and less manual prompt juggling?

The project does not try to replace a human writer. Its goal is to make the writing process more controllable: separate story planning from draft generation, keep model settings reproducible, and record enough generation context to debug why a draft succeeds or fails.

## What It Does

The pipeline has four layers:

- **Story planning**: builds a structured outline with title, premise, character roles, emotional arc, reversals, and beat planning.
- **Prompt orchestration**: converts the plan into execution prompts designed for a local Qwen model.
- **Continuous generation**: generates a full short story by target word count instead of traditional chapters, while feeding the previous segment back into the next request to improve continuity.
- **Memory and QA loop**: stores confirmed facts, unresolved hooks, recent summaries, segment tails, and lightweight quality checks after every generated segment.

The current default target is a Chinese short story in the 10,000-30,000 word range. Generated drafts are stored locally under `books/`, but they are ignored by Git so the repository stays focused on the system itself.

## Why I Built It

Most simple LLM writing workflows fail in predictable ways: the model forgets earlier context, changes character relationships, writes too short, or drifts away from the intended emotional rhythm. This project treats those failures as engineering problems.

The pipeline therefore includes:

- configurable model profiles for local inference
- target-word driven generation
- segment-level progress output
- previous-context feedback between segments
- automatic continuation when a segment is too short
- generation logs for debugging context handoff
- a persistent `story_state.json` file for continuity debugging
- a `quality_report.md` file that flags short output, weak first-person usage, weak openings, and likely transition issues
- a persistent `generation_state.json` file for pause/resume and crash recovery
- optional chapter-style generation for long-form projects

This makes the project closer to a small writing systems tool than a single prompt.

## Project Structure

```text
config/
  qianwen_sets/              # Legacy JSON model profiles
  story_presets/             # Story type presets and target structure

knowledge/
  fanqie_short_rules.md      # Research notes and short-story rhythm rules

prompts/
  controller/                # Planning/controller prompt templates
  qianwen/                   # Draft-generation prompt templates

src/fanqie_pipeline/
  memory.py                  # Persistent story-state model across segments
  model/                     # Unified model client, config, and providers
  outline.py                 # Outline validation for longer targets
  planner.py                 # Builds the outline and segment prompts
  quality.py                 # Lightweight generated-text checks
  qianwen_client.py          # Backward-compatible wrapper around model/
  run.py                     # Command-line entry point
  state.py                   # Pause/resume generation state
```

Local generated books are written to:

```text
books/short_story/<book-id>/
```

That folder is intentionally ignored by Git.

## Requirements

- Python 3.10+
- A local or remote OpenAI-compatible chat completions endpoint
- Ollama is supported by default for local inference

## Model Configuration

The application uses one model interface regardless of where the model runs:

```python
response = model_client.generate(
    messages=messages,
    temperature=temperature,
    max_tokens=max_tokens,
)
```

Novel generation code does not branch on local vs remote models. Provider switching is handled by `src/fanqie_pipeline/model/`.

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

`.env` is ignored by Git so API keys do not get committed.

### Local Model

Use this when running Ollama or another local OpenAI-compatible server:

```env
MODEL_PROVIDER=local
LOCAL_MODEL_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_MODEL_NAME=hf.co/Qwen/Qwen3-14B-GGUF:Q4_K_M
LOCAL_API_KEY=ollama
```

Defaults if `.env` is missing:

```text
MODEL_PROVIDER=local
LOCAL_MODEL_BASE_URL=http://127.0.0.1:11434/v1
hf.co/Qwen/Qwen3-14B-GGUF:Q4_K_M
MODEL_TEMPERATURE=0.82
MODEL_TOP_P=0.92
MODEL_MAX_TOKENS=4096
MODEL_TIMEOUT_SECONDS=1200
```

### Remote API Model

Use this for OpenAI or another OpenAI-compatible remote API:

```env
MODEL_PROVIDER=api
API_MODEL_BASE_URL=https://api.openai.com/v1
API_MODEL_NAME=gpt-4o-mini
API_KEY=your_api_key_here
```

If `MODEL_PROVIDER=api` and `API_KEY` is missing, the program exits with a readable configuration error.

### Environment Variables

| Variable | Meaning | Default |
| --- | --- | --- |
| `MODEL_PROVIDER` | `local` or `api` | `local` |
| `LOCAL_MODEL_BASE_URL` | Local OpenAI-compatible base URL | `http://127.0.0.1:11434/v1` |
| `LOCAL_MODEL_NAME` | Local model name | `hf.co/Qwen/Qwen3-14B-GGUF:Q4_K_M` |
| `LOCAL_API_KEY` | Optional local API key placeholder | `ollama` |
| `API_MODEL_BASE_URL` | Remote API base URL | `https://api.openai.com/v1` |
| `API_MODEL_NAME` | Remote model name | `gpt-4o-mini` |
| `API_KEY` | Remote API key | required for `api` |
| `MODEL_TEMPERATURE` | Sampling temperature | `0.82` |
| `MODEL_TOP_P` | Top-p sampling | `0.92` |
| `MODEL_MAX_TOKENS` | Max output tokens per request | `4096` |
| `MODEL_TIMEOUT_SECONDS` | Request timeout | `1200` |
| `MODEL_REPEAT_PENALTY` | Repeat penalty if provider supports it | `1.08` |
| `MODEL_PRESENCE_PENALTY` | Optional presence penalty | omitted |
| `MODEL_FREQUENCY_PENALTY` | Optional frequency penalty | omitted |
| `MODEL_SEED` | Optional deterministic seed | omitted |

Legacy JSON profiles under `config/qianwen_sets/` still work through `--qianwen-set`, but `.env` is the preferred configuration path.

## Usage

Generate only the outline and final Qwen prompt:

```powershell
python -m src.fanqie_pipeline.run `
  --topic "妻子为了白月光逼我离婚，离婚当天我继承千亿集团" `
  --book-id "lihun-qianyi" `
  --mode prompt `
  --target-words 20000
```

Generate a continuous short-story draft:

```powershell
python -m src.fanqie_pipeline.run `
  --topic "妻子为了白月光逼我离婚，离婚当天我继承千亿集团" `
  --book-id "lihun-qianyi" `
  --mode generate `
  --target-words 20000 `
  --segment-words 2000
```

Generate a long-form draft in chapter mode:

```powershell
python -m src.fanqie_pipeline.run `
  --topic "被赶出家门后，我成了首富" `
  --book-id "long-novel-demo" `
  --mode generate `
  --style chapters `
  --book-type long `
  --target-words 1000000 `
  --segment-words 2500 `
  --max-units-per-run 5
```

For a million-word run, use `--max-units-per-run` and generate in batches. This avoids losing a long session to a local model or GPU failure.

Resume after stopping, crashing, or reaching the batch limit:

```powershell
python -m src.fanqie_pipeline.run `
  --topic "被赶出家门后，我成了首富" `
  --book-id "long-novel-demo" `
  --mode generate `
  --style chapters `
  --book-type long `
  --target-words 1000000 `
  --segment-words 2500 `
  --resume
```

Pause cleanly after the current chapter finishes by creating this file inside the book folder:

```text
books/long/long-novel-demo/pause.flag
```

For slower local GPUs, increase the request timeout:

```powershell
python -m src.fanqie_pipeline.run `
  --topic "妻子为了白月光逼我离婚，离婚当天我继承千亿集团" `
  --book-id "lihun-qianyi" `
  --mode generate `
  --timeout-seconds 1800
```

Use the 32B model profile:

```powershell
python -m src.fanqie_pipeline.run `
  --topic "妻子为了白月光逼我离婚，离婚当天我继承千亿集团" `
  --book-id "lihun-qianyi" `
  --mode generate `
  --qianwen-set config/qianwen_sets/ollama_qwen3_32b.json
```

Prefer `.env` for new model settings. Use `--qianwen-set` only when you specifically want one of the legacy JSON profiles.

Unload the Ollama model after generation to free GPU memory:

```powershell
python -m src.fanqie_pipeline.run `
  --topic "妻子为了白月光逼我离婚，离婚当天我继承千亿集团" `
  --book-id "lihun-qianyi" `
  --mode generate `
  --unload-after
```

## Output Files

Each generated book folder contains:

```text
outline.md              # Structured plan
qianwen_prompt.md        # Final execution prompt
generation_log.md        # Context handoff and segment previews
story_state.json         # Persistent story memory
generation_state.json    # Resume checkpoint and progress state
outline_report.md        # Outline warnings for long targets
quality_report.md        # Segment-level QA notes
drafts/segment_001.md    # Generated text segment
final/novel.md           # Merged story draft
metadata.json            # Topic and configuration metadata
```

## Current Limitations

This is an early local-generation pipeline, not a polished writing product. The generated story quality still depends heavily on the model, prompt design, and decoding settings. The next improvements I would prioritize are:

- stronger long-context memory beyond heuristic fact tracking
- automated consistency checks for names, relationships, and timeline events
- a review pass that flags weak transitions or repeated emotional beats
- optional revision passes that rewrite weak segments instead of only flagging them

## Notes

The repository is designed to be reproducible and inspectable. Model settings live in JSON files, planning rules live in Markdown, and generation artifacts are kept out of version control by default.
