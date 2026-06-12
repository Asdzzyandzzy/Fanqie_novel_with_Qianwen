# Fanqie Short Story Pipeline with Local Qwen

This repository is a local LLM writing pipeline for structured Chinese short-story generation. It started as a practical experiment: how can a local Qwen model be guided to produce a complete Fanqie-style short story with stronger continuity, clearer pacing, and less manual prompt juggling?

The project does not try to replace a human writer. Its goal is to make the writing process more controllable: separate story planning from draft generation, keep model settings reproducible, and record enough generation context to debug why a draft succeeds or fails.

## What It Does

The pipeline has three layers:

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
  qianwen_sets/              # Local model endpoint and decoding settings
  story_presets/             # Story type presets and target structure

knowledge/
  fanqie_short_rules.md      # Research notes and short-story rhythm rules

prompts/
  controller/                # Planning/controller prompt templates
  qianwen/                   # Draft-generation prompt templates

src/fanqie_pipeline/
  memory.py                  # Persistent story-state model across segments
  outline.py                 # Outline validation for longer targets
  planner.py                 # Builds the outline and segment prompts
  quality.py                 # Lightweight generated-text checks
  qianwen_client.py          # Calls local Qwen through an OpenAI-compatible API
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
- A local OpenAI-compatible LLM endpoint
- Ollama is supported by default

The default model profile points to:

```text
http://127.0.0.1:11434/v1/chat/completions
hf.co/Qwen/Qwen3-14B-GGUF:Q4_K_M
```

A 32B profile is also included:

```text
config/qianwen_sets/ollama_qwen3_32b.json
```

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
