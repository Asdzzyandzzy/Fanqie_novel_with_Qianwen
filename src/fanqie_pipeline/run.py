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
        get_segment_beats,
        save_book_files,
    )
    from src.fanqie_pipeline.memory import StoryMemory
    from src.fanqie_pipeline.quality import append_quality_report, inspect_segment
    from src.fanqie_pipeline.qianwen_client import call_qianwen, load_qianwen_set, unload_qianwen_model
else:
    from .planner import (
        build_chapter_prompt,
        build_plan,
        build_segment_continuation_prompt,
        build_segment_prompt,
        get_segment_beats,
        save_book_files,
    )
    from .memory import StoryMemory
    from .quality import append_quality_report, inspect_segment
    from .qianwen_client import call_qianwen, load_qianwen_set, unload_qianwen_model


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="番茄爆款短篇小说总控系统")
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
        help="continuous=番茄短故事一篇完结不分章；chapters=旧版按章生成",
    )
    parser.add_argument("--segment-words", type=int, default=2000, help="连续短故事每段目标字数")
    parser.add_argument("--context-chars", type=int, default=2600, help="回喂上一段结尾多少字")
    parser.add_argument("--min-segment-chars", type=int, default=1600, help="低于这个长度会自动续写补足")
    parser.add_argument("--max-repair-rounds", type=int, default=2, help="单段太短时最多补写几次")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="单次请求千问最长等待秒数；本地慢卡可设 1200 或 1800")
    parser.add_argument("--unload-after", action="store_true", help="生成完成后卸载 Ollama 模型，释放显存")
    parser.add_argument(
        "--chapters",
        default="all",
        help="生成哪些章节：all 或数字，例如 1。默认 all，会让千问连续生成全篇。",
    )
    parser.add_argument(
        "--qianwen-set",
        default=str(ROOT / "config" / "qianwen_sets" / "local_openai_compatible.json"),
        help="千问参数配置文件",
    )
    args = parser.parse_args()

    plan = build_plan(
        topic=args.topic,
        target_words=args.target_words,
        chapter_count=args.chapter_count,
    )
    paths = save_book_files(ROOT, args.book_type, args.book_id, plan)

    if args.mode == "generate":
        try:
            qianwen_set = load_qianwen_set(Path(args.qianwen_set))
            if args.timeout_seconds is not None:
                qianwen_set["timeout_seconds"] = args.timeout_seconds
            _log(f"已连接配置：{qianwen_set.get('name', 'unknown')} / {qianwen_set.get('model', 'unknown')}")
            _log(f"单次请求最长等待：{qianwen_set.get('timeout_seconds', 180)} 秒")
            if args.style == "chapters":
                output_paths, final_path = _generate_chapters(args, paths, plan, qianwen_set)
            else:
                output_paths, final_path = _generate_continuous(args, paths, plan, qianwen_set)
            if args.unload_after:
                _log("正在卸载本地模型以释放显存...")
                unload_qianwen_model(qianwen_set)
                _log("模型卸载请求已发送。")
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "message": str(exc),
                        "outline": str(paths["outline"]),
                        "prompt": str(paths["prompt"]),
                        "fix": "启动本地千问 OpenAI 兼容服务，或修改 --qianwen-set 指向正确的配置文件。",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            sys.exit(1)
        result = {
            "status": "generated",
            "style": args.style,
            "outline": str(paths["outline"]),
            "prompt": str(paths["prompt"]),
            "outputs": [str(path) for path in output_paths],
            "final": str(final_path),
        }
    else:
        result = {
            "status": "planned",
            "outline": str(paths["outline"]),
            "prompt": str(paths["prompt"]),
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


def _generate_continuous(args: argparse.Namespace, paths: dict[str, Path], plan, qianwen_set: dict) -> tuple[list[Path], Path]:
    segment_count = max(1, math.ceil(args.target_words / max(args.segment_words, 1)))
    output_paths = []
    memory = StoryMemory.from_plan(plan)
    _log(f"准备生成连续短文：目标 {args.target_words} 字，约 {segment_count} 段，每段约 {args.segment_words} 字")
    _log(f"输出目录：{paths['drafts']}")
    log_path = paths["book_dir"] / "generation_log.md"
    state_path = paths["book_dir"] / "story_state.json"
    quality_path = paths["book_dir"] / "quality_report.md"
    log_path.write_text(
        f"# 生成日志\n\n目标字数：{args.target_words}\n\n分段字数：{args.segment_words}\n\n回喂字数：{args.context_chars}\n\n",
        encoding="utf-8",
    )
    quality_path.write_text("# Quality Report\n\n", encoding="utf-8")

    for segment_number in range(1, segment_count + 1):
        started_at = time.time()
        _log(f"[{segment_number}/{segment_count}] 第{segment_number}段开始生成...")
        memory_context = memory.build_prompt_block(args.context_chars)
        prompt = build_segment_prompt(
            plan=plan,
            segment_number=segment_number,
            segment_count=segment_count,
            segment_words=args.segment_words,
            memory_context=memory_context,
        )
        segment_text = call_qianwen(prompt, qianwen_set)
        segment_text = _repair_short_segment(
            args=args,
            plan=plan,
            qianwen_set=qianwen_set,
            segment_text=segment_text,
            segment_number=segment_number,
            segment_count=segment_count,
        )
        segment_path = paths["drafts"] / f"segment_{segment_number:03d}.md"
        segment_path.write_text(segment_text, encoding="utf-8")
        output_paths.append(segment_path)
        local_beats = get_segment_beats(plan, segment_number, segment_count)
        quality_report = inspect_segment(
            text=segment_text,
            segment_number=segment_number,
            min_chars=args.min_segment_chars,
            previous_tail=memory.recent_tail,
        )
        append_quality_report(quality_path, quality_report)
        _append_generation_log(log_path, segment_number, segment_count, memory_context, segment_text, args.context_chars)
        memory.record_segment(segment_number, segment_text, local_beats, args.context_chars)
        memory.save(state_path)
        elapsed = time.time() - started_at
        qa_status = "通过" if quality_report.passed else "有问题"
        _log(f"[{segment_number}/{segment_count}] 第{segment_number}段完成，用时 {elapsed:.1f}s，约 {len(segment_text)} 字，QA：{qa_status}：{segment_path}")

    final_path = paths["final"] / "novel.md"
    _merge_outputs(output_paths, final_path)
    _log(f"已合并连续成稿：{final_path}")
    _log(f"生成日志：{log_path}")
    _log(f"故事状态：{state_path}")
    _log(f"质量报告：{quality_path}")
    return output_paths, final_path


def _generate_chapters(args: argparse.Namespace, paths: dict[str, Path], plan, qianwen_set: dict) -> tuple[list[Path], Path]:
    chapter_numbers = _resolve_chapters(args.chapters, args.chapter_count)
    chapter_paths = []
    total = len(chapter_numbers)
    _log(f"准备生成 {total} 章，输出目录：{paths['drafts']}")
    for index, chapter_number in enumerate(chapter_numbers, start=1):
        started_at = time.time()
        _log(f"[{index}/{total}] 第{chapter_number}章开始生成...")
        chapter_prompt = build_chapter_prompt(plan, chapter_number, args.chapter_count)
        chapter_text = call_qianwen(chapter_prompt, qianwen_set)
        chapter_path = paths["drafts"] / f"chapter_{chapter_number:03d}.md"
        chapter_path.write_text(chapter_text, encoding="utf-8")
        chapter_paths.append(chapter_path)
        elapsed = time.time() - started_at
        _log(f"[{index}/{total}] 第{chapter_number}章完成，用时 {elapsed:.1f}s，约 {len(chapter_text)} 字：{chapter_path}")

    final_path = paths["final"] / "novel.md"
    _merge_outputs(chapter_paths, final_path)
    _log(f"已合并成稿：{final_path}")
    return chapter_paths, final_path


def _repair_short_segment(args: argparse.Namespace, plan, qianwen_set: dict, segment_text: str, segment_number: int, segment_count: int) -> str:
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
        addition = call_qianwen(repair_prompt, qianwen_set)
        segment_text = segment_text.rstrip() + "\n\n" + addition.strip()
    return segment_text


def _merge_chapters(drafts_dir: Path, final_path: Path) -> None:
    chapter_files = sorted(drafts_dir.glob("chapter_*.md"))
    _merge_outputs(chapter_files, final_path)


def _merge_outputs(output_paths: list[Path], final_path: Path) -> None:
    content = []
    for path in output_paths:
        content.append(path.read_text(encoding="utf-8").strip())
    final_path.write_text("\n\n".join(content) + "\n", encoding="utf-8")


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
