from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

if __package__ in (None, ""):
    # 兼容直接运行：python src/fanqie_pipeline/run.py
    # 正常推荐：python -m src.fanqie_pipeline.run
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from src.fanqie_pipeline.planner import (
        build_chapter_prompt,
        build_plan,
        build_segment_continuation_prompt,
        build_segment_prompt,
        build_segment_revision_prompt,
        get_segment_beats,
        save_book_files,
    )
    from src.fanqie_pipeline.memory import StoryMemory
    from src.fanqie_pipeline.outline import inspect_outline, write_outline_report
    from src.fanqie_pipeline.quality import append_quality_report, inspect_segment
    from src.fanqie_pipeline.state import GenerationState
    from src.fanqie_pipeline.model import ModelClient
else:
    from .planner import (
        build_chapter_prompt,
        build_plan,
        build_segment_continuation_prompt,
        build_segment_prompt,
        build_segment_revision_prompt,
        get_segment_beats,
        save_book_files,
    )
    from .memory import StoryMemory
    from .outline import inspect_outline, write_outline_report
    from .quality import append_quality_report, inspect_segment
    from .state import GenerationState
    from .model import ModelClient


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="本地 Qwen 长短篇小说生成管线")
    parser.add_argument("--topic", required=True, help="题材或核心梗，例如：妻子为了白月光逼我离婚")
    parser.add_argument("--book-id", required=True, help="书籍目录名，只用英文、数字、短横线更稳")
    parser.add_argument("--mode", choices=["outline", "prompt", "generate"], default="prompt")
    parser.add_argument("--book-type", default="short_story", help="默认 short_story；以后长篇可用 long")
    parser.add_argument("--target-words", type=int, default=20000, help="目标总字数，可微调；番茄短故事建议10000-30000字")
    parser.add_argument("--chapter-count", type=int, default=6, help="章节数，可微调")
    parser.add_argument(
        "--style",
        choices=["continuous", "chapters"],
        default="continuous",
        help="continuous=短故事连续分段；chapters=长篇按章生成并保留断点",
    )
    parser.add_argument("--segment-words", type=int, default=2000, help="连续短故事每段目标字数")
    parser.add_argument("--context-chars", type=int, default=2600, help="回喂上一段结尾多少字")
    parser.add_argument("--min-segment-chars", type=int, default=1600, help="低于这个长度会自动续写补足")
    parser.add_argument("--max-repair-rounds", type=int, default=2, help="单段太短时最多补写几次")
    parser.add_argument("--max-revision-rounds", type=int, default=1, help="质量检查失败时最多重写几次")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="单次请求千问最长等待秒数；本地慢卡可设 1200 或 1800")
    parser.add_argument("--unload-after", action="store_true", help="生成完成后卸载 Ollama 模型，释放显存")
    parser.add_argument("--resume", action="store_true", help="从 generation_state.json 和 story_state.json 断点继续")
    parser.add_argument("--stop-file", default="pause.flag", help="生成中如果书籍目录出现该文件，则当前单元完成后暂停")
    parser.add_argument("--max-units-per-run", type=int, default=None, help="本次最多生成多少个单元，便于分批跑百万字")
    parser.add_argument(
        "--chapters",
        default="all",
        help="生成哪些章节：all 或数字，例如 1。默认 all，会让千问连续生成全篇。",
    )
    parser.add_argument(
        "--qianwen-set",
        default=None,
        help="旧版 JSON 模型配置文件；不传则使用 .env / 环境变量",
    )
    parser.add_argument("--env-file", default=str(ROOT / ".env"), help=".env 配置文件路径")
    args = parser.parse_args()

    plan = build_plan(
        topic=args.topic,
        target_words=args.target_words,
        chapter_count=args.chapter_count,
    )
    paths = save_book_files(ROOT, args.book_type, args.book_id, plan)
    total_units = _resolve_total_units(args)
    outline_report = inspect_outline(plan, args.target_words, total_units)
    write_outline_report(paths["book_dir"] / "outline_report.md", outline_report)

    if args.mode == "generate":
        try:
            model_client = _build_model_client(args)
            if args.timeout_seconds is not None:
                model_client.config.timeout_seconds = args.timeout_seconds
            _log(f"已连接模型：{model_client.config.display_name}")
            _log(f"单次请求最长等待：{model_client.config.timeout_seconds} 秒")
            if args.style == "chapters":
                output_paths, final_path = _generate_units(args, paths, plan, model_client, unit_kind="chapter")
            else:
                output_paths, final_path = _generate_units(args, paths, plan, model_client, unit_kind="segment")
            if args.unload_after:
                _log("正在卸载本地模型以释放显存...")
                model_client.unload()
                _log("模型卸载请求已发送。")
        except KeyboardInterrupt:
            _mark_generation_state(paths["book_dir"], "paused", "用户中断。")
            print(
                json.dumps(
                    {
                        "status": "paused",
                        "message": "检测到中断，已保存断点。下次使用 --resume 继续。",
                        "state": str(paths["book_dir"] / "generation_state.json"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            sys.exit(130)
        except Exception as exc:
            _mark_generation_state(paths["book_dir"], "error", str(exc))
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": str(exc),
                        "outline": str(paths["outline"]),
                        "prompt": str(paths["prompt"]),
                        "fix": "检查 .env / 环境变量，或启动本地 OpenAI-compatible 模型服务。",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            sys.exit(1)
        result = {
            "status": _read_generation_status(paths["book_dir"]) or "generated",
            "style": args.style,
            "outline": str(paths["outline"]),
            "prompt": str(paths["prompt"]),
            "generation_state": str(paths["book_dir"] / "generation_state.json"),
            "story_state": str(paths["book_dir"] / "story_state.json"),
            "quality_report": str(paths["book_dir"] / "quality_report.md"),
            "outputs": [str(path) for path in output_paths],
            "final": str(final_path),
        }
    else:
        result = {
            "status": "planned",
            "outline": str(paths["outline"]),
            "prompt": str(paths["prompt"]),
            "outline_report": str(paths["book_dir"] / "outline_report.md"),
            "next": "确认本地千问服务已启动后，把 --mode 改成 generate 生成正文。",
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))


def _resolve_chapters(chapters: str, chapter_count: int) -> list[int]:
    if chapters == "all":
        return list(range(1, chapter_count + 1))
    chapter_number = int(chapters)
    if chapter_number < 1 or chapter_number > chapter_count:
        raise ValueError(f"--chapters 必须在 1 到 {chapter_count} 之间，或使用 all")
    return [chapter_number]


def _build_model_client(args: argparse.Namespace) -> ModelClient:
    env_path = Path(args.env_file) if args.env_file else None
    if args.qianwen_set:
        return ModelClient.from_config_file(Path(args.qianwen_set), env_path=env_path)
    return ModelClient.from_env(env_path=env_path)


def _mark_generation_state(book_dir: Path, status: str, message: str) -> None:
    state_path = book_dir / "generation_state.json"
    if not state_path.exists():
        return
    state = GenerationState.load(state_path)
    if status == "paused":
        state.mark_paused()
    else:
        state.mark_error(message)
    state.save(state_path)


def _read_generation_status(book_dir: Path) -> str | None:
    state_path = book_dir / "generation_state.json"
    if not state_path.exists():
        return None
    return GenerationState.load(state_path).status


def _resolve_total_units(args: argparse.Namespace) -> int:
    if args.style == "chapters" and args.chapter_count > 0:
        return max(args.chapter_count, math.ceil(args.target_words / max(args.segment_words, 1)))
    return max(1, math.ceil(args.target_words / max(args.segment_words, 1)))


def _generate_units(args: argparse.Namespace, paths: dict[str, Path], plan, model_client: ModelClient, unit_kind: str) -> tuple[list[Path], Path]:
    total_units = _resolve_total_units(args)
    output_paths = []
    state_path = paths["book_dir"] / "generation_state.json"
    memory_path = paths["book_dir"] / "story_state.json"
    stop_path = paths["book_dir"] / args.stop_file
    memory = StoryMemory.load(memory_path) if args.resume and memory_path.exists() else StoryMemory.from_plan(plan)
    state = (
        GenerationState.load(state_path)
        if args.resume and state_path.exists()
        else GenerationState.create(
            book_id=args.book_id,
            book_type=args.book_type,
            style=args.style,
            target_words=args.target_words,
            unit_words=args.segment_words,
            total_units=total_units,
        )
    )
    state.status = "running"
    state.save(state_path)
    memory.save(memory_path)

    unit_name = "章" if unit_kind == "chapter" else "段"
    _log(f"准备生成：目标 {args.target_words} 字，约 {total_units} {unit_name}，每{unit_name}约 {args.segment_words} 字")
    _log(f"当前断点：从第 {state.next_unit} {unit_name}开始，已生成约 {state.current_chars} 字")
    _log(f"输出目录：{paths['drafts']}")
    log_path = paths["book_dir"] / "generation_log.md"
    quality_path = paths["book_dir"] / "quality_report.md"
    if not args.resume or not log_path.exists():
        log_path.write_text(
            f"# 生成日志\n\n目标字数：{args.target_words}\n\n单元字数：{args.segment_words}\n\n回喂字数：{args.context_chars}\n\n",
            encoding="utf-8",
        )
    if not args.resume or not quality_path.exists():
        quality_path.write_text("# Quality Report\n\n", encoding="utf-8")

    generated_this_run = 0
    for unit_number in range(state.next_unit, total_units + 1):
        if args.max_units_per_run is not None and generated_this_run >= args.max_units_per_run:
            state.mark_paused()
            state.save(state_path)
            _log(f"达到本次生成上限 --max-units-per-run={args.max_units_per_run}，已暂停。")
            break
        if stop_path.exists():
            state.mark_paused()
            state.save(state_path)
            _log(f"检测到暂停文件：{stop_path}。当前不会启动新{unit_name}，状态已保存。")
            break
        started_at = time.time()
        _log(f"[{unit_number}/{total_units}] 第{unit_number}{unit_name}开始生成...")
        memory_context = memory.build_prompt_block(args.context_chars)
        prompt = build_segment_prompt(
            plan=plan,
            segment_number=unit_number,
            segment_count=total_units,
            segment_words=args.segment_words,
            memory_context=memory_context,
            unit_label=unit_name,
        )
        segment_text = model_client.generate(messages=_messages(prompt))
        segment_text = _repair_short_segment(
            args=args,
            plan=plan,
            model_client=model_client,
            segment_text=segment_text,
            segment_number=unit_number,
            segment_count=total_units,
        )
        local_beats = get_segment_beats(plan, unit_number, total_units)
        quality_report = inspect_segment(
            text=segment_text,
            segment_number=unit_number,
            min_chars=args.min_segment_chars,
            previous_tail=memory.recent_tail,
        )
        segment_text, quality_report = _revise_failed_segment(
            args=args,
            plan=plan,
            model_client=model_client,
            segment_text=segment_text,
            quality_report=quality_report,
            segment_number=unit_number,
            segment_count=total_units,
            memory_context=memory_context,
            unit_label=unit_name,
            previous_tail=memory.recent_tail,
        )
        prefix = "chapter" if unit_kind == "chapter" else "segment"
        segment_path = paths["drafts"] / f"{prefix}_{unit_number:04d}.md"
        segment_path.write_text(segment_text, encoding="utf-8")
        output_paths.append(segment_path)
        append_quality_report(quality_path, quality_report)
        _append_generation_log(log_path, unit_number, total_units, memory_context, segment_text, args.context_chars)
        memory.record_segment(unit_number, segment_text, local_beats, args.context_chars)
        memory.save(memory_path)
        state.record_unit(unit_number, segment_path, len(segment_text), quality_report.passed)
        state.save(state_path)
        generated_this_run += 1
        elapsed = time.time() - started_at
        qa_status = "通过" if quality_report.passed else "有问题"
        _log(f"[{unit_number}/{total_units}] 第{unit_number}{unit_name}完成，用时 {elapsed:.1f}s，约 {len(segment_text)} 字，QA：{qa_status}：{segment_path}")
        if state.is_complete:
            _log(f"目标完成：当前累计约 {state.current_chars} 字，状态 {state.status}。")
            break

    final_path = paths["final"] / "novel.md"
    all_outputs = _collect_outputs(paths["drafts"], unit_kind)
    _merge_outputs(all_outputs, final_path)
    _log(f"已合并成稿：{final_path}")
    _log(f"生成日志：{log_path}")
    _log(f"生成状态：{state_path}")
    _log(f"故事记忆：{memory_path}")
    _log(f"质量报告：{quality_path}")
    return all_outputs, final_path


def _generate_chapters(args: argparse.Namespace, paths: dict[str, Path], plan, model_client: ModelClient) -> tuple[list[Path], Path]:
    chapter_numbers = _resolve_chapters(args.chapters, args.chapter_count)
    chapter_paths = []
    total = len(chapter_numbers)
    _log(f"准备生成 {total} 章，输出目录：{paths['drafts']}")
    for index, chapter_number in enumerate(chapter_numbers, start=1):
        started_at = time.time()
        _log(f"[{index}/{total}] 第{chapter_number}章开始生成...")
        chapter_prompt = build_chapter_prompt(plan, chapter_number, args.chapter_count)
        chapter_text = model_client.generate(messages=_messages(chapter_prompt))
        chapter_path = paths["drafts"] / f"chapter_{chapter_number:03d}.md"
        chapter_path.write_text(chapter_text, encoding="utf-8")
        chapter_paths.append(chapter_path)
        elapsed = time.time() - started_at
        _log(f"[{index}/{total}] 第{chapter_number}章完成，用时 {elapsed:.1f}s，约 {len(chapter_text)} 字：{chapter_path}")

    final_path = paths["final"] / "novel.md"
    _merge_outputs(chapter_paths, final_path)
    _log(f"已合并成稿：{final_path}")
    return chapter_paths, final_path


def _repair_short_segment(args: argparse.Namespace, plan, model_client: ModelClient, segment_text: str, segment_number: int, segment_count: int) -> str:
    for round_number in range(1, args.max_repair_rounds + 1):
        if len(segment_text) >= args.min_segment_chars:
            return segment_text
        missing = args.min_segment_chars - len(segment_text)
        _log(f"[{segment_number}/{segment_count}] 当前只有约 {len(segment_text)} 字，补写第 {round_number} 轮，至少再补 {missing} 字...")
        repair_prompt = build_segment_continuation_prompt(
            plan=plan,
            segment_number=segment_number,
            segment_count=segment_count,
            missing_words=max(500, missing),
            current_segment_tail=segment_text[-args.context_chars :],
        )
        addition = model_client.generate(messages=_messages(repair_prompt))
        segment_text = segment_text.rstrip() + "\n\n" + addition.strip()
    return segment_text


def _revise_failed_segment(
    args: argparse.Namespace,
    plan,
    model_client: ModelClient,
    segment_text: str,
    quality_report,
    segment_number: int,
    segment_count: int,
    memory_context: str,
    unit_label: str,
    previous_tail: str,
) -> tuple[str, object]:
    for round_number in range(1, args.max_revision_rounds + 1):
        if quality_report.passed:
            return segment_text, quality_report
        issues = [issue.message for issue in quality_report.issues if issue.level == "error"]
        if not issues:
            return segment_text, quality_report
        _log(f"[{segment_number}/{segment_count}] QA失败，开始第 {round_number} 轮重写：{'; '.join(issues)}")
        revision_prompt = build_segment_revision_prompt(
            plan=plan,
            segment_number=segment_number,
            segment_count=segment_count,
            segment_words=args.segment_words,
            memory_context=memory_context,
            rejected_text=segment_text,
            issues=issues,
            unit_label=unit_label,
        )
        segment_text = model_client.generate(messages=_messages(revision_prompt))
        segment_text = _repair_short_segment(
            args=args,
            plan=plan,
            model_client=model_client,
            segment_text=segment_text,
            segment_number=segment_number,
            segment_count=segment_count,
        )
        quality_report = inspect_segment(
            text=segment_text,
            segment_number=segment_number,
            min_chars=args.min_segment_chars,
            previous_tail=previous_tail,
        )
    return segment_text, quality_report


def _messages(prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "/no_think\n"
                "你是番茄短故事执行作者。"
                "必须保持第一人称、强连续性、高冲突、高反转、高情绪密度，只输出正文。"
            ),
        },
        {"role": "user", "content": "/no_think\n" + prompt},
    ]


def _merge_chapters(drafts_dir: Path, final_path: Path) -> None:
    chapter_files = sorted(drafts_dir.glob("chapter_*.md"))
    _merge_outputs(chapter_files, final_path)


def _merge_outputs(output_paths: list[Path], final_path: Path) -> None:
    content = []
    for path in output_paths:
        content.append(path.read_text(encoding="utf-8").strip())
    final_path.write_text("\n\n".join(content) + "\n", encoding="utf-8")


def _collect_outputs(drafts_dir: Path, unit_kind: str) -> list[Path]:
    prefix = "chapter" if unit_kind == "chapter" else "segment"
    return sorted(drafts_dir.glob(f"{prefix}_*.md"))


def _append_generation_log(
    log_path: Path,
    segment_number: int,
    segment_count: int,
    memory_context: str,
    segment_text: str,
    context_chars: int,
) -> None:
    preview = segment_text[:500].replace("\n", "\n> ")
    tail = segment_text[-context_chars:].replace("\n", "\n> ")
    memory = memory_context[-5000:].replace("\n", "\n> ") if memory_context else "无"
    with log_path.open("a", encoding="utf-8") as file:
        file.write(f"## 第{segment_number}/{segment_count}段\n\n")
        file.write(f"### 回喂记忆\n\n> {memory}\n\n")
        file.write(f"### 本段开头预览\n\n> {preview}\n\n")
        file.write(f"### 本段留给下一段的尾巴\n\n> {tail}\n\n")


def _log(message: str) -> None:
    print(message, flush=True)


if __name__ == "__main__":
    main()
