from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List

from .planner import StoryPlan


@dataclass
class SegmentRecord:
    """单个生成段的压缩记忆。"""

    segment_number: int
    char_count: int
    opening: str
    ending: str
    summary: str


@dataclass
class StoryMemory:
    """跨段生成记忆。

    本地模型长文生成最容易丢的是人物关系、已发生事实和未解决钩子。
    这个对象把这些信息显式写回下一段 Prompt，而不是只依赖模型上下文。
    """

    title: str
    topic: str
    protagonist: str
    heroine: str
    villain: str
    core_emotion: str
    confirmed_facts: List[str] = field(default_factory=list)
    unresolved_hooks: List[str] = field(default_factory=list)
    used_beats: List[str] = field(default_factory=list)
    long_term_memory: List[str] = field(default_factory=list)
    short_term_memory: List[str] = field(default_factory=list)
    character_states: List[str] = field(default_factory=list)
    segment_records: List[SegmentRecord] = field(default_factory=list)
    recent_tail: str = ""

    @classmethod
    def from_plan(cls, plan: StoryPlan) -> "StoryMemory":
        return cls(
            title=plan.title,
            topic=plan.topic,
            protagonist=plan.protagonist,
            heroine=plan.heroine,
            villain=plan.villain,
            core_emotion=plan.core_emotion,
            confirmed_facts=[
                "全文优先第一人称“我”。",
                "主角被亲密关系误解和压迫，但真实身份更强。",
                "女主前期误信反派，后期后悔和占有欲爆发。",
                "反派靠伪证、舆论或道德绑架制造阻碍。",
            ],
            unresolved_hooks=[
                "主角真实身份需要逐步曝光，不能一次讲完。",
                "女主误会的真相需要分批揭开。",
                "白月光或反派的伪证需要被更强证据反噬。",
            ],
            long_term_memory=[
                "主线方向：压迫、误解、证据、身份曝光、情感后悔必须持续升级。",
                "长线约束：已发生事实不能反写，人物动机不能突然变脸。",
                "爽点节奏：每个生成单元至少推进一个冲突、一个情绪变化或一个证据节点。",
            ],
            character_states=[
                "主角：被压迫但掌握隐藏资源，行动目标是尊严、真相和清算。",
                "女主：前期误判，后期后悔；不能无理由立刻洗白。",
                "反派：持续制造阻碍，每次胜利都要为后续反噬埋证据。",
            ],
        )

    @classmethod
    def load(cls, path: Path) -> "StoryMemory":
        data = json.loads(path.read_text(encoding="utf-8"))
        data["segment_records"] = [SegmentRecord(**item) for item in data.get("segment_records", [])]
        return cls(**data)

    def build_prompt_block(self, context_chars: int) -> str:
        records = self.segment_records[-4:]
        summaries = "\n".join(f"- 第{item.segment_number}段：{item.summary}" for item in records) or "- 暂无，当前是开头。"
        facts = "\n".join(f"- {item}" for item in self.confirmed_facts[-12:])
        hooks = "\n".join(f"- {item}" for item in self.unresolved_hooks[-8:])
        beats = "\n".join(f"- {item}" for item in self.used_beats[-10:]) or "- 暂无。"
        long_term = "\n".join(f"- {item}" for item in self.long_term_memory[-14:])
        short_term = "\n".join(f"- {item}" for item in self.short_term_memory[-8:]) or "- 暂无。"
        character_states = "\n".join(f"- {item}" for item in self.character_states[-10:])
        tail = self.recent_tail[-context_chars:].strip() or "无。"
        return f"""【故事记忆】
标题：{self.title}
题材：{self.topic}
主角：{self.protagonist}
女主：{self.heroine}
反派：{self.villain}
核心情绪：{self.core_emotion}

【已确认事实，不许写反】
{facts}

【长期记忆：全书级约束】
{long_term}

【人物状态：不能突变】
{character_states}

【短期记忆：最近几段的动作与情绪】
{short_term}

【最近剧情摘要】
{summaries}

【已使用爆点，避免原地重复】
{beats}

【未解决钩子，后文要继续推进】
{hooks}

【上一段结尾原文，必须无缝承接】
<<<
{tail}
>>>"""

    def record_segment(self, segment_number: int, text: str, used_beats: List[str], context_chars: int) -> None:
        clean = _compact_text(text)
        opening = clean[:260]
        ending = clean[-520:]
        summary = _summarize_segment(clean)
        self.segment_records.append(
            SegmentRecord(
                segment_number=segment_number,
                char_count=len(clean),
                opening=opening,
                ending=ending,
                summary=summary,
            )
        )
        self.used_beats.extend(used_beats)
        self.recent_tail = clean[-context_chars:]
        self._update_hooks_from_text(clean)
        _append_unique(self.short_term_memory, f"第{segment_number}段：{summary}")
        self.short_term_memory = self.short_term_memory[-12:]

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    def _update_hooks_from_text(self, text: str) -> None:
        if "离婚" in text and ("签" in text or "协议" in text):
            _append_unique(self.confirmed_facts, "离婚协议或婚姻切割已经进入明面冲突。")
            _append_unique(self.long_term_memory, "婚姻切割是主角翻盘的起点，后续不能写成无事发生。")
        if "录音" in text or "证据" in text:
            _append_unique(self.confirmed_facts, "证据线已经出现，后文需要持续兑现。")
            _append_unique(self.long_term_memory, "证据链是打脸核心，后续需要升级证据而不是只靠解释。")
        if "身份" in text or "集团" in text or "继承" in text:
            _append_unique(self.confirmed_facts, "主角隐藏身份线已经被读者感知，后文需要阶梯式曝光。")
            _append_unique(self.long_term_memory, "身份曝光必须带来实际行动后果，例如资源、权力、反派崩盘。")
        if "救命恩人" in text or "当年" in text:
            _append_unique(self.confirmed_facts, "当年旧事或救命恩人线已经进入剧情。")
        if "跪" in text or "崩溃" in text:
            _append_unique(self.confirmed_facts, "反派或女主已经出现情绪/地位反转。")
        if "女主" in text and ("后悔" in text or "哭" in text or "崩溃" in text):
            _append_unique(self.character_states, "女主后悔值上升，但不能轻易获得主角原谅。")
        if "白月光" in text and ("慌" in text or "脸色" in text or "证据" in text):
            _append_unique(self.character_states, "反派已经感到压力，后续会更激进地反扑。")

        if "真相" in text or "当年" in text:
            _append_unique(self.unresolved_hooks, "当年真相必须继续拆解，不能只提不收。")
        if "录音" in text or "证据" in text:
            _append_unique(self.unresolved_hooks, "证据链需要继续升级，不能只靠口头解释。")
        if "集团" in text or "身份" in text:
            _append_unique(self.unresolved_hooks, "主角身份曝光必须带来实际权力打脸。")

        if "全部真相" in text or "终于明白" in text:
            _remove_matching(self.unresolved_hooks, ["当年真相"])


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "\n", text.strip())


def _summarize_segment(text: str) -> str:
    sentences = re.split(r"(?<=[。！？!?])", text)
    selected = [item.strip() for item in sentences if item.strip()]
    if not selected:
        return text[:180]
    head = "".join(selected[:2])
    tail = "".join(selected[-2:])
    summary = head if head == tail else head + " / " + tail
    return summary[:360]


def _append_unique(items: List[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _remove_matching(items: List[str], keywords: List[str]) -> None:
    items[:] = [item for item in items if not any(keyword in item for keyword in keywords)]
