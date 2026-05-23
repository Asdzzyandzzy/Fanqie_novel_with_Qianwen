# 番茄爆款短故事小说总控系统

这个项目把“爆款编辑脑”和“千问写作执行”拆开：

- `knowledge/`：番茄短篇、红果短剧、爽文节奏规则库。
- `config/qianwen_sets/`：本地千问模型、接口地址、温度、字数等参数配置。
- `config/story_presets/`：不同类型书的结构预设，短篇、长篇以后都放这里。
- `prompts/`：总控系统提示词、千问正文执行模板。
- `books/`：每本书的专属资产，大纲、Prompt、章节草稿、成稿都在这里。
- `src/fanqie_pipeline/`：调用总控、生成大纲、拼装 Prompt、调用千问的代码。

## 快速开始

先生成一本番茄短故事的总控方案和千问 Prompt：

```powershell
python -m src.fanqie_pipeline.run --topic "妻子为了白月光逼我离婚，离婚当天我继承千亿集团" --book-id "lihun-qianyi" --mode prompt --target-words 20000
```

如果你的本地千问已经提供 OpenAI 兼容接口，再生成正文：

```powershell
python -m src.fanqie_pipeline.run --topic "妻子为了白月光逼我离婚，离婚当天我继承千亿集团" --book-id "lihun-qianyi" --mode generate --target-words 20000
```

默认 `--style continuous`，会按总字数切成连续段落调用千问，不显示章节标题。每段会自动回喂上一段结尾，避免前后不搭。

生成：

```text
drafts/segment_001.md
drafts/segment_002.md
...
final/novel.md
generation_log.md
```

只想小规模测试：

```powershell
python -m src.fanqie_pipeline.run --topic "妻子为了白月光逼我离婚，离婚当天我继承千亿集团" --book-id "lihun-qianyi-test" --mode generate --target-words 6000 --segment-words 2000
```

默认接口配置在：

```text
config/qianwen_sets/local_openai_compatible.json
```

当前默认适配 Ollama：

```text
http://127.0.0.1:11434/v1/chat/completions
hf.co/Qwen/Qwen3-14B-GGUF:Q4_K_M
```

如果想用 32B：

```powershell
python -m src.fanqie_pipeline.run --topic "妻子为了白月光逼我离婚，离婚当天我继承千亿集团" --book-id "lihun-qianyi" --mode generate --qianwen-set config/qianwen_sets/ollama_qwen3_32b.json
```

如果你换成 vLLM、LM Studio 或其他服务，把配置里的 `base_url`、`model`、`temperature`、`max_tokens` 改成实际参数即可。

本地显卡生成慢时，不要急着停。14B/32B 一段 2000 字可能跑几分钟。默认 14B 已设为等待 1200 秒，也可以命令行临时改：

```powershell
python -m src.fanqie_pipeline.run --topic "妻子为了白月光逼我离婚，离婚当天我继承千亿集团" --book-id "lihun-qianyi" --mode generate --timeout-seconds 1800
```

## 每本书的文件位置

运行后会生成：

```text
books/
  short_story/
    lihun-qianyi/
      outline.md              # 总控大纲：标题、人设、节奏、爆点、反转
      qianwen_prompt.md        # 最终给千问执行的 Prompt
      generation_log.md        # 每段回喂了什么、下一段承接什么
      drafts/
        segment_001.md         # 千问生成的连续正文片段
      final/
        novel.md               # 一篇完结短故事
      metadata.json            # 题材、类型、生成时间、配置来源
```

## 调参位置

- 想改模型参数：改 `config/qianwen_sets/local_openai_compatible.json`
- 想改短故事节奏：改 `config/story_presets/fanqie_short.json`
- 想改爆款规则：改 `knowledge/fanqie_short_rules.md`
- 想改千问写作约束：改 `prompts/qianwen/fanqie_short_executor.md`
