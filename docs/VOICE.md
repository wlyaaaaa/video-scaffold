# 配音指南 · Fish Audio 情感与音效标记

旁白文案里可以内嵌 Fish 的标记来控制**演绎**。标记是被模型解析的，不会被读出来
（实测 `[long pause]` 会增加停顿但不会念出 "long pause"）。让 AI 写文案时**适度**
使用这些标记，让央视音色更有张力——但别滥用，正经攻略以 `[emphasis]` / `[pause]`
/ `[excited]` 为主即可。

## 情感语调（包住要带情绪的那句）
`[angry] [sad] [embarrassed] [emphasis] [whispering] [soft] [breathy] [excited]`

## 音效 / 停顿（插在发生的位置）
`[laughing] [chuckling] [moaning] [clear throat] [sobbing] [crying loudly]`
`[sighing] [panting] [groaning] [crowd laughing] [background laughter]`
`[audience laughing] [pause] [long pause]`

## 写法示例
```
传说级武器，正式解禁！[excited] 今天，带你拆解这件硬核装备的核心部件。
先看阻抗强度，接着是展开兼容，最后是续航能力。[emphasis] 三项核心数据，全面拉满。
```

## 注意
- 标记照常进入 TTS 文本（`pipeline/fish_tts.py` 原样发送）。
- 标记**不会**进入 Whisper 转写（转写的是合成出来的语音），所以 `data-cue` 仍然
  cue 真实读出的词，不受标记影响。
- 规范列表见 `config.py` 的 `FISH_EMOTION_TAGS` / `FISH_SFX_TAGS`。
