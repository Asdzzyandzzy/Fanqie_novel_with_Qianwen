from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class StoryPlan:
    """总控生成的结构化方案，后续会保存成 Markdown 给人看、给千问执行。"""

    topic: str
    title: str
    sell_point: str
    core_emotion: str
    protagonist: str
    heroine: str
    villain: str
    first_three_chapters: List[str]
    full_beats: List[str]
    beat_500_words: List[str]
    reversals: List[str]
    ending_hook: str
    qianwen_prompt: str


def build_plan(topic: str, target_words: int = 12000, chapter_count: int = 6) -> StoryPlan:
    """根据题材生成短篇总控大纲。

    这里先用可控模板保证节奏稳定；后续你可以接入更强的“选题分析模型”，
    只要返回同样字段，后面的千问执行层不用改。
    """

    topic = topic.strip() or "离婚当天，我继承千亿集团"
    title = _build_title(topic)
    chapter_words = max(1200, target_words // max(chapter_count, 1))
    beat_count = max(8, target_words // 500)

    first_three = [
        f"第1章：100字内切入背叛或离婚危机；300字内抛出主角隐藏身份线索。反派当众羞辱，女主误信白月光，主角签字离开，结尾让顶级人物跪迎主角。",
        f"第2章：反派借舆论继续压迫，主角被全网嘲笑。主角不解释，直接用第一个底牌打脸。女主第一次动摇，但白月光反咬一口，结尾升级到更大危机。",
        f"第3章：白月光设局让主角身败名裂。主角反手放出证据，反派第一次崩盘。女主后悔感爆发，却发现主角身边出现更偏爱他的强势人物。",
    ]

    full_beats = [
        "开局背叛：女主或亲近关系站到反派那边，主角被逼到绝境。",
        "羞辱压迫：反派当众踩主角，让读者替主角憋屈。",
        "隐藏身份：主角被赶走后，顶级身份露出冰山一角。",
        "第一次打脸：反派刚宣布主角完了，证据或大人物立刻反杀。",
        "女主后悔：她发现自己误解主角，但主角已经不回头。",
        "危机升级：白月光或幕后黑手制造更大的舆论、商业、生命危机。",
        "极端偏爱：强势新角色只护主角，公开撕碎反派体面。",
        "连环反转：每次反派以为翻盘，都会暴露更深罪证。",
        "终局审判：主角公开亮出全部身份和证据，让所有人跪下。",
        "余钩：女主拿到迟来的真相，发现当年救她的人其实是主角。",
    ]

    beat_500 = _build_500_word_beats(beat_count)
    reversals = [
        "反转1：众人以为主角净身出户，实际他主动切割有毒关系。",
        "反转2：反派拿出的证据是假的，真正录音在主角手里。",
        "反转3：女主以为白月光救过她，当年的救命恩人其实是主角。",
        "反转4：主角不是被资本选中，而是资本真正的主人。",
        "反转5：幕后黑手不是外人，而是一直操控女主误会的人。",
    ]
    ending_hook = "终章打脸后，女主在旧物里发现主角当年为她险些丧命的证据；她追到机场，却看见主角身边站着真正懂他、护他的女人。"

    qianwen_prompt = build_qianwen_prompt(
        topic=topic,
        title=title,
        target_words=target_words,
        chapter_count=chapter_count,
        chapter_words=chapter_words,
        first_three=first_three,
        full_beats=full_beats,
        beat_500=beat_500,
        reversals=reversals,
        ending_hook=ending_hook,
    )

    return StoryPlan(
        topic=topic,
        title=title,
        sell_point="第一人称强代入：我被最亲近的人踩进泥里后，用隐藏身份连环翻盘，让背叛者悔到崩溃。",
        core_emotion="极致委屈后的极致打脸；误解、背叛、翻盘、后悔、偏爱连续拉满。",
        protagonist="第一人称男主：表面落魄、被婚姻和家族抛弃，实际掌握顶级资源。我不爱解释，只用结果打脸；目标是切断旧关系、查清当年真相、夺回尊严。",
        heroine="女主：现实、骄傲、曾误解我，被白月光操控。前期冷漠压迫，后期后悔失控，占有欲和愧疚感一起爆炸。",
        villain="反派：白月光或伪精英，靠谎言吃女主资源，擅长舆论构陷和道德绑架。每次嘴硬都会被更狠证据打脸。",
        first_three_chapters=first_three,
        full_beats=full_beats,
        beat_500_words=beat_500,
        reversals=reversals,
        ending_hook=ending_hook,
        qianwen_prompt=qianwen_prompt,
    )


def render_plan_markdown(plan: StoryPlan) -> str:
    """严格按用户要求的栏目输出总控方案。"""

    return "\n\n".join(
        [
            f"【题材】\n{plan.topic}",
            f"【爆款标题】\n{plan.title}",
            f"【一句话卖点】\n{plan.sell_point}",
            f"【核心情绪】\n{plan.core_emotion}",
            f"【主角设定】\n{plan.protagonist}",
            f"【女主设定】\n{plan.heroine}",
            f"【反派设定】\n{plan.villain}",
            "【前三章节奏】\n" + "\n".join(f"- {item}" for item in plan.first_three_chapters),
            "【全篇爽点规划】\n" + "\n".join(f"- {item}" for item in plan.full_beats),
            "【每500字爆点规划】\n" + "\n".join(f"- {item}" for item in plan.beat_500_words),
            "【反转节点】\n" + "\n".join(f"- {item}" for item in plan.reversals),
            f"【结尾钩子】\n{plan.ending_hook}",
            f"【最终给Qianwen的Prompt】\n{plan.qianwen_prompt}",
        ]
    )


def build_qianwen_prompt(
    topic: str,
    title: str,
    target_words: int,
    chapter_count: int,
    chapter_words: int,
    first_three: List[str],
    full_beats: List[str],
    beat_500: List[str],
    reversals: List[str],
    ending_hook: str,
) -> str:
    """拼装给千问的最终执行 Prompt。"""

    return f"""/no_think

你是番茄小说短故事执行作者。请严格按下面总控方案写一篇连续完结短故事。

书名：{title}
题材：{topic}
目标总字数：约{target_words}字
生成批次：{chapter_count}段
每段字数：约{chapter_words}字

强制写法：
1. 短句，高频对话，高频冲突，高频推进。
2. 100字内必须出现背叛、离婚、羞辱、危机或打脸。
3. 300字内必须出现巨大钩子、身份反差、第一次反转或核心悬念。
4. 每800-1200字至少出现一个爆点：打脸、反转、危机升级、身份曝光、情绪爆发、极端偏爱、翻盘。
5. 每个生成段落结尾必须留钩，但最终成稿不要章节标题。
6. 禁止文学风、慢热、长环境描写、大段心理活动、解释世界观、无意义聊天。
7. 优先第一人称“我”，增强代入感。

前三章节奏：
{_as_numbered(first_three)}

全篇爽点：
{_as_numbered(full_beats)}

每500字爆点表：
{_as_numbered(beat_500)}

反转节点：
{_as_numbered(reversals)}

结尾钩子：
{ending_hook}

请先输出第1段正文。只写正文，不要解释创作思路。"""


def build_chapter_prompt(plan: StoryPlan, chapter_number: int, chapter_count: int) -> str:
    """为单章生成更精确的千问执行 Prompt。

    千问每次只写一章，更容易控制节奏、爆点和结尾钩子。
    """

    chapter_goal = _chapter_goal(chapter_number, chapter_count)
    local_beats = _chapter_beats(plan.beat_500_words, chapter_number, chapter_count)
    return f"""/no_think

你是番茄短篇、红果短剧风网文执行作者。只写第{chapter_number}章正文。

书名：{plan.title}
题材：{plan.topic}

本章任务：
{chapter_goal}

本章必须使用的500字爆点：
{_as_numbered(local_beats)}

全篇不可违背的反转：
{_as_numbered(plan.reversals)}

强制写法：
1. 开头100字内必须爆冲突，不许铺垫。
2. 300字内必须出现身份反差、危机升级或第一次反转。
3. 每500字至少一个爆点。
4. 高频对话，短句，强情绪，强压迫，强打脸。
5. 章节结尾必须留钩。
6. 禁止文学风、慢热、长环境描写、大段心理活动、无意义对白、解释世界观。

只输出第{chapter_number}章正文。不要输出分析、标题解释、创作说明。"""


def build_segment_prompt(
    plan: StoryPlan,
    segment_number: int,
    segment_count: int,
    segment_words: int,
    memory_context: str,
) -> str:
    """为信息流短文生成连续分段 Prompt。

    这里不要求“第几章”，而是按总字数切成连续段落。每段回喂上一段尾巴，
    让模型承接人物、地点、证据、情绪和动作，减少前后不搭。
    """

    phase = _segment_phase(segment_number, segment_count)
    local_beats = _segment_beats(plan.beat_500_words, segment_number, segment_count)
    memory_block = memory_context.strip() or "无。这是正文开头，必须100字内爆冲突。"
    return f"""/no_think

你是番茄小说短故事执行作者。现在写一篇连续完结短故事的第{segment_number}/{segment_count}段，不要写章节标题。

书名：{plan.title}
题材：{plan.topic}
本段目标字数：至少{segment_words}字，尽量写满，不要几百字就收。
本段剧情位置：{phase}

{memory_block}

承接规则：
1. 第一段开头100字内必须爆冲突。
2. 如果不是第一段，第一句话必须紧接上一段最后的动作、对白或悬念，不许换场硬跳。
3. 不许改名，不许改人物关系，不许把已经发生的事写反。
4. 本段必须继续推进，不许总结前文，不许重讲上一段。
5. 每800-1200字至少一个爆点：打脸、反转、危机升级、身份曝光、情绪爆发、极端偏爱、翻盘。
6. 段尾必须留钩，但不要写“未完待续”。
7. 优先使用第一人称“我”，不要突然切成上帝视角。

本段必须吃掉的爆点：
{_as_numbered(local_beats)}

全篇爽点方向：
{_as_numbered(plan.full_beats)}

全篇反转底线：
{_as_numbered(plan.reversals)}

语言硬规则：
短句。高频对话。高频冲突。高频推进。番茄短故事风。网文语言。第一人称强代入。
禁止文学腔、慢热、长环境描写、大段心理活动、无意义对白、解释世界观。

只输出正文，不要标题、不要大纲、不要分析。"""


def build_segment_continuation_prompt(
    plan: StoryPlan,
    segment_number: int,
    segment_count: int,
    missing_words: int,
    current_segment_tail: str,
) -> str:
    """当模型写太短时，要求它无缝续写当前段。"""

    return f"""/no_think

你刚才写的第{segment_number}/{segment_count}段太短。现在无缝续写当前段，至少再写{missing_words}字。

书名：{plan.title}
题材：{plan.topic}

当前段结尾原文：
<<<
{current_segment_tail}
>>>

续写要求：
1. 第一自然段必须紧接上面的最后一句，不许跳场。
2. 继续制造压迫、打脸、反转或危机升级。
3. 不许总结，不许重复前文，不许写章节标题。
4. 段尾继续留钩。

只输出续写正文。"""


def save_book_files(root: Path, book_type: str, book_id: str, plan: StoryPlan) -> Dict[str, Path]:
    """把一本书的总控产物保存到固定目录。"""

    book_dir = root / "books" / book_type / book_id
    drafts_dir = book_dir / "drafts"
    final_dir = book_dir / "final"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    outline_path = book_dir / "outline.md"
    prompt_path = book_dir / "qianwen_prompt.md"
    metadata_path = book_dir / "metadata.json"

    outline_path.write_text(render_plan_markdown(plan), encoding="utf-8")
    prompt_path.write_text(plan.qianwen_prompt, encoding="utf-8")
    metadata_path.write_text(
        _metadata_json(plan.topic, plan.title, book_type),
        encoding="utf-8",
    )

    return {
        "book_dir": book_dir,
        "outline": outline_path,
        "prompt": prompt_path,
        "drafts": drafts_dir,
        "final": final_dir,
        "metadata": metadata_path,
    }


def _build_title(topic: str) -> str:
    if "离婚" in topic and "继承" in topic:
        return "《离婚当天，我继承了千亿集团》"
    if "赶出" in topic or "赶出家门" in topic:
        return "《被赶出家门后，我成了首富》"
    if "白月光" in topic:
        return "《妻子为了白月光，把我逼成了首富》"
    if "同学会" in topic:
        return "《同学会装穷，校花当场崩溃》"
    return f"《{topic}》"


def _build_500_word_beats(count: int) -> List[str]:
    beat_cycle = [
        "0-500字：开局爆冲突，亲密关系背叛，主角被当众羞辱。",
        "500-1000字：反派加码压迫，主角被逼签字或背锅。",
        "1000-1500字：第一个身份线索出现，大人物对主角异常恭敬。",
        "1500-2000字：反派嘴硬嘲讽，主角用证据第一次打脸。",
        "2000-2500字：女主开始动摇，但白月光制造新误会。",
        "2500-3000字：危机升级到舆论或商业封杀，主角表面更惨。",
        "3000-3500字：主角亮出第二张底牌，反派计划反噬。",
        "3500-4000字：女主后悔爆发，想挽回却被主角冷处理。",
        "4000-4500字：极端偏爱角色登场，公开站队主角。",
        "4500-5000字：反派最后一搏，牵出当年真相。",
        "5000-5500字：主角查到幕后黑手，旧案反转。",
        "5500-6000字：女主发现救命恩人真相，情绪崩溃。",
        "6000-6500字：反派绑架、构陷或夺权，危机升级。",
        "6500-7000字：主角反杀，幕后势力第一次露怯。",
        "7000-7500字：所有人以为主角输了，顶级身份正式曝光。",
        "7500-8000字：反派社死，女主跪求解释机会。",
        "8000-8500字：主角拒绝回头，新的感情偏爱加深。",
        "8500-9000字：幕后黑手抛出最后筹码，逼主角二选一。",
        "9000-9500字：主角用隐藏证据终局翻盘。",
        "9500-10000字：反派跪下，女主悔到失控。",
        "10000-10500字：当年真相完全揭开，主角完成情绪清算。",
        "10500-11000字：女主最后挽回失败，读者获得爽感释放。",
        "11000-11500字：主角走向新关系或新权力位置。",
        "11500-12000字：终章留钩，旧物揭示更深秘密或下一部入口。",
    ]
    return beat_cycle[:count]


def _as_numbered(items: List[str]) -> str:
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


def _chapter_goal(chapter_number: int, chapter_count: int) -> str:
    goals = {
        1: "开局背叛和离婚压迫拉满。反派当众羞辱主角，女主误信反派。主角签字离开，结尾出现顶级人物跪迎主角。",
        2: "反派用舆论继续踩主角。主角第一次公开打脸，女主动摇。白月光立刻制造新误会，结尾危机升级。",
        3: "白月光设局让主角身败名裂。主角反手放证据，反派第一次崩盘。女主后悔感爆发，强势偏爱角色登场。",
    }
    if chapter_number in goals:
        return goals[chapter_number]
    if chapter_number == chapter_count:
        return "终局审判。主角亮出全部身份和证据，反派跪下，女主悔到崩溃。结尾用旧物或真相留余钩。"
    return "危机继续升级。反派以为自己翻盘，实际一步步暴露罪证。主角逐层亮底牌，女主后悔和占有欲持续加深。"


def _chapter_beats(beats: List[str], chapter_number: int, chapter_count: int) -> List[str]:
    if not beats:
        return []
    per_chapter = max(1, len(beats) // max(chapter_count, 1))
    start = (chapter_number - 1) * per_chapter
    if chapter_number == chapter_count:
        return beats[start:]
    return beats[start : start + per_chapter]


def _segment_phase(segment_number: int, segment_count: int) -> str:
    ratio = segment_number / max(segment_count, 1)
    if segment_number == 1:
        return "开头留人：背叛、离婚、羞辱、危机、身份反差必须快速出现。"
    if ratio < 0.35:
        return "前段加压：反派连续踩主角，主角露出第一批底牌，读者憋屈后立刻获得打脸。"
    if ratio < 0.7:
        return "中段升级：误会加深、女主后悔、反派设局，主角每次翻盘都牵出更大危机。"
    if segment_number == segment_count:
        return "终局收束：身份总曝光、证据总清算、反派跪下、女主悔崩，并留下余味钩子。"
    return "后段爆发：连环反转、极端偏爱、幕后黑手露面，主角掌控全局。"


def _segment_beats(beats: List[str], segment_number: int, segment_count: int) -> List[str]:
    if not beats:
        return []
    per_segment = max(1, len(beats) // max(segment_count, 1))
    start = (segment_number - 1) * per_segment
    if segment_number == segment_count:
        return beats[start:]
    return beats[start : start + per_segment]


def get_segment_beats(plan: StoryPlan, segment_number: int, segment_count: int) -> List[str]:
    """供运行层记录当前段消费了哪些节奏点。"""

    return _segment_beats(plan.beat_500_words, segment_number, segment_count)


def _metadata_json(topic: str, title: str, book_type: str) -> str:
    # 手写 JSON 是为了避免引入额外依赖；字段固定，内容已做最小转义。
    safe_topic = topic.replace("\\", "\\\\").replace('"', '\\"')
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    return (
        "{\n"
        f'  "topic": "{safe_topic}",\n'
        f'  "title": "{safe_title}",\n'
        f'  "book_type": "{book_type}",\n'
        '  "preset": "fanqie_short",\n'
        '  "qianwen_set": "local_openai_compatible"\n'
        "}\n"
    )
