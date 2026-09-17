# 配音指南 · Fish Audio 情感与音效标记

旁白文案里可以内嵌 Fish 的标记来控制**演绎**。标记是被模型解析的，不会被读出来
（实测 `[long pause]` 会增加停顿但不会念出 "long pause"）。让 AI 写文案时**适度**
使用这些标记，让云飞声线更有张力——但别滥用，信息型旁白通常以 `[emphasis]` /
`[pause]` / `[excited]` 为主即可。

## 情感语调（包住要带情绪的那句）
`[angry] [sad] [embarrassed] [emphasis] [whispering] [soft] [breathy] [excited]`

## 音效 / 停顿（插在发生的位置）
`[laughing] [chuckling] [moaning] [clear throat] [sobbing] [crying loudly]`
`[sighing] [panting] [groaning] [crowd laughing] [background laughter]`
`[audience laughing] [pause] [long pause]`

## 写法示例
```
先说结论。[emphasis] 这个变化会影响三个关键环节。[pause]
接下来，我们逐项拆开来看。
```

## 注意
- 标记照常进入 TTS 文本（`pipeline/fish_tts.py` 原样发送）。
- 标记**不会**进入 Whisper 转写（转写的是合成出来的语音），所以 `data-cue` 仍然
  cue 真实读出的词，不受标记影响。
- 规范列表见 `config.py` 的 `FISH_EMOTION_TAGS` / `FISH_SFX_TAGS`。

## 时间来源与质量边界

默认继续使用 Whisper；VIDEO_TIMING_SOURCE=fish 是明确选择的原生时间戳适配。切换来源必须重新生成配音与时间轴，不混用旧来源记录。协议解析测试不等于对真实账户、声线、中文发音及情感标记的验收；具体调用与验证边界见 WORKFLOW.md。所有真实配音请求均是显式操作，普通诊断及合成演示不消耗账户额度。
