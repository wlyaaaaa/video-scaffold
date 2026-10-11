# 本期影片

在 video-scaffold 根目录运行命令；影片内容留在此目录。默认白底绿，图文页分镜表驱动画面。

| 分镜表 | 出片 | 状态 |
|---|---|---|
| `pages/intro.json` | `_samples/checkpoint/intro.mp4` | 6 秒流程试片，合成测试音；不代表配音或视觉审定 |

开工：核对本期文案与已有素材，填入真实配音、原文与词轴，编写分镜表；通用模块在 video-scaffold 修改，本期分镜、图片、成片留在这里。

```powershell
python -m pipeline.pages <本期/pages/intro.json> plan
python -m pipeline.pages <本期/pages/intro.json> stills
python -m pipeline.pages <本期/pages/intro.json> render
```

生产配音放 `narration/`，图片放 `art/`，其他素材放 `assets/`。示例 WAV 是合成测试音，时间轴仅用于测试，不要把它登记为真实配音。生成新版本使用新文件名。

AI 取法，可改：先看 6 秒、再看 30 秒、再看完整第一段；经主持把关及本人审定后分段并行。已通过的表与成片保留；修改共用版式先比较既有页面。详细字段、分工与派单模板见底座 AGENTS.md、docs/AUTHORING.md、docs/WORKFLOW.md。
