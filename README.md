# wechat-token-saver

**WeChat article reader · filter invalid images · save token**

[中文](#中文) · [English](#english)

---

<a id="中文"></a>

## 中文

把微信公众号文章抓成 **Markdown 正文 + 本地配图 + 图片优先级清单**。

别的工具帮你把文章抓下来；这个工具还告诉你**哪几张图值得让 AI 读**——过滤掉装饰图、头像、二维码，只读有信息量的那几张，省下真金白银的 token。

一个命令，不需要登录、不需要浏览器、不需要 API Key。

### 和同类工具的区别

| | 普通公众号转 Markdown 工具 | wechat-token-saver |
|---|---|---|
| 正文转 Markdown | ✅ | ✅ |
| 图片下载到本地 | ✅ | ✅ |
| **图片按信息密度排序** | ❌ | ✅ |
| **标注哪几张值得读** | ❌ | ✅ 优先读 / 可选 / 可跳过 |
| **为 AI 省 token** | ❌ | ✅ 只读关键图，跳过装饰图 |

一篇 23 张配图的文章，全塞给 AI 约需 25000 token；用这个工具挑出 3 张「优先读」，约 4000 token。

### 相关项目

如果你要的是**更强的反爬能力**或 **MCP Server**，下面两个项目更成熟，推荐直接用：

- [jackwener/wechat-article-to-markdown](https://github.com/jackwener/wechat-article-to-markdown) — Camoufox 反检测、PyPI 发布、live E2E 测试
- [bzd6661/wechat-article-for-ai](https://github.com/bzd6661/wechat-article-for-ai) — MCP Server + Skill、异步并发下载、音视频提取

wechat-token-saver 专注一件事：**图片优先级判断，让 AI 精读时少花 token**。

### 为什么做这个

公众号文章有两个麻烦：

1. **链接会失效**，图片防盗链，收藏了也可能打不开
2. **关键信息常在图里**（数据图、流程图、对比表），纯文本抓取会丢掉

这个工具把正文和图片一起落到本地，并额外生成一份「图片清单」——按信息密度排序，标注哪几张图值得读。

### 安装

需要 Python 3.10+。

```bash
pip install wechat-token-saver
```

或从源码安装：

```bash
git clone https://github.com/Jiang-70/wechat-token-saver.git
cd wechat-token-saver
pip install -e .
```

### 使用

**抓一篇文章**

```bash
wechat-token-saver https://mp.weixin.qq.com/s/xxxxx
```

**批量抓取**

```bash
wechat-token-saver URL1 URL2 URL3 -o ./my_articles
```

或从文件读取（每行一个链接，`#` 开头是注释）：

```bash
wechat-token-saver --from-file links.txt
```

**查看已抓文章**

```bash
wechat-token-saver --list
```

**只要正文不要图**

```bash
wechat-token-saver URL --no-images
```

**输出 YAML frontmatter**（方便接入 Obsidian 等知识库）

```bash
wechat-token-saver URL --yaml
```

默认输出引用块格式的元数据；加 `--yaml` 后改成标准 YAML frontmatter：

```yaml
---
title: "文章标题"
account: "公众号名"
date: "2026-11-23 07:56"
source: "https://mp.weixin.qq.com/s/xxxxx"
description: "摘要"
---
```

**网络不稳时**

程序内置指数退避重试（1/2/4/8 秒，上限 30 秒）和验证码显式检测。遇到「环境异常」会直接报 `CaptchaError`，不会白白重试浪费时间。可调整：

```bash
wechat-token-saver URL --timeout 60 --retries 5
```

**输出 JSON**（方便脚本处理）

```bash
wechat-token-saver URL --json
```

**配置默认路径**

用环境变量，不必每次敲 `-o`：

```bash
export WECHAT_TOKEN_SAVER_OUTPUT=~/Documents/wechat_articles
# Windows PowerShell:
# $env:WECHAT_TOKEN_SAVER_OUTPUT = "$HOME\Documents\wechat_articles"
```

### 输出结构

```
articles/
├── _index.json                     # 全部文章索引
└── 文章标题/
    ├── 文章标题.md                 # 正文，图片引用已本地化
    ├── images/
    │   ├── img_001.jpg
    │   └── ...
    ├── image_manifest.md           # 图片清单（按信息密度排序）
    └── meta.json                   # 标题/公众号/时间/字数/配图数
```

**图片清单长什么样**

| 文件 | 尺寸 | KB | 上下文 | 建议 | 分值 |
|---|---|---|---|---|---|
| images/img_005.jpg | 863x1004 | 93.9 | …Gemini最适合的位置，是坐在Claude旁边… | **优先读** | 70 |
| images/img_009.jpg | 783x495 | 35.4 | …需要GPT在最后把一道关… | **优先读** | 40 |
| images/img_003.jpg | 346x373 | 87.4 | …GPT反正是信息密度最高的… | 可跳过 | 5 |

排序算法不是单纯按像素，而是结合：

- 图片相邻文字里有没有「如下」「流程」「结构」等提示词
- 长宽比（近方形多为结构图，明显偏宽多为表格/时间线）
- 图片面积

**用途**：让 AI 只读值得读的图，避免把几十张装饰图全塞进上下文浪费 token。

### Python API

```python
from wechat_token_saver import fetch_article, ArticleFetcher

# 最简单
result = fetch_article("https://mp.weixin.qq.com/s/xxxxx")
print(result.title, result.account, result.char_count)

# 复用配置批量抓
fetcher = ArticleFetcher("./articles", timeout=30, retries=3)
results = fetcher.fetch_many([
    "https://mp.weixin.qq.com/s/aaa",
    "https://mp.weixin.qq.com/s/bbb",
])
for r in results:
    for image in r.images:
        if image.priority == "优先读":
            print(image.file, image.context)
```

### 注意事项

**链接必须是微信自己生成的**：

- 短链 `https://mp.weixin.qq.com/s/xxxxx` ✅
- 完整长链（带 `__biz&mid&idx&sn&chksm`）✅
- 自己手拼的参数链接（缺 `chksm`）❌ 会返回「环境异常」

获取方式：公众号文章页 → 右上角「···」→ **复制链接**。

**网络**：程序会从你的机器直接访问 `mp.weixin.qq.com`，不经过任何第三方服务器。图片下载带 `Referer` 头绕过防盗链。

**频率**：程序默认每次抓取后 sleep 1 秒，批量抓取时请勿调低，避免触发风控。

### 常见错误

| 提示 | 原因 | 处理 |
|---|---|---|
| 返回「环境异常」 | 链接被风控或参数不全 | 重新用微信「复制链接」；等几分钟再试 |
| 配图数量偏少 | 部分图片防盗链拦截 | 正常现象，核心图通常会保留 |
| `captcha` 相关错误 | 请求频率过高或 UA 被识别 | 降低频率；不要用精简 UA |

### 开发

```bash
pip install -e ".[dev]"
pytest
```

### 使用约定

欢迎个人使用、学习和二次开发。若用于商业产品或对外服务，请：

- 保留原作者署名与本项目链接
- 告知我一声（GitHub Issue 或私信都行）
- 如果它帮你省了钱，star 一下就是最好的支持

这是约定而非法律条款；法律上的权利与限制以 LICENSE 为准。

### License

MIT — 允许商用与修改，但必须保留版权声明和许可证文本。

### 免责声明

本工具仅用于个人归档与学习，请尊重原作者版权，不要用于批量爬取或商业分发他人内容。

---

<a id="english"></a>

## English

Turn WeChat Official Account articles into **Markdown text + local images + an image priority manifest**.

Other tools download the article. This one also tells you **which images are actually worth feeding to an AI** — it filters out decorations, avatars and QR codes, so you only read the figures that carry information and save real money on tokens.

One command. No login, no browser, no API key.

### How it differs

| | Typical WeChat-to-Markdown tools | wechat-token-saver |
|---|---|---|
| Article body to Markdown | ✅ | ✅ |
| Download images locally | ✅ | ✅ |
| **Rank images by information density** | ❌ | ✅ |
| **Mark which ones are worth reading** | ❌ | ✅ must-read / optional / skip |
| **Save tokens for AI** | ❌ | ✅ read key figures, skip decorations |

For an article with 23 images, feeding all of them to an AI costs roughly 25,000 tokens. Picking 3 "must-read" ones with this tool costs about 4,000.

### Related projects

If you need **stronger anti-bot capability** or an **MCP Server**, these two projects are more mature — go straight to them:

- [jackwener/wechat-article-to-markdown](https://github.com/jackwener/wechat-article-to-markdown) — Camoufox anti-detection, PyPI release, live E2E tests
- [bzd6661/wechat-article-for-ai](https://github.com/bzd6661/wechat-article-for-ai) — MCP Server + Skill, async concurrent downloads, audio/video extraction

wechat-token-saver does one thing: **image priority ranking, so AI close-reading costs fewer tokens**.

### Why this exists

WeChat articles have two problems:

1. **Links rot**, images are hotlink-protected, and saved articles may stop opening
2. **Key information often lives in images** (charts, flow diagrams, comparison tables) that plain-text scrapers lose

This tool saves the text and images locally, and generates an extra "image manifest" — ranked by information density, flagging which images are worth reading.

### Installation

Requires Python 3.10+.

```bash
pip install wechat-token-saver
```

Or from source:

```bash
git clone https://github.com/Jiang-70/wechat-token-saver.git
cd wechat-token-saver
pip install -e .
```

### Usage

**Fetch one article**

```bash
wechat-token-saver https://mp.weixin.qq.com/s/xxxxx
```

**Fetch multiple**

```bash
wechat-token-saver URL1 URL2 URL3 -o ./my_articles
```

Or read URLs from a file (one per line, `#` starts a comment):

```bash
wechat-token-saver --from-file links.txt
```

**List saved articles**

```bash
wechat-token-saver --list
```

**Text only, no images**

```bash
wechat-token-saver URL --no-images
```

**YAML frontmatter** (for Obsidian and other knowledge bases)

```bash
wechat-token-saver URL --yaml
```

By default metadata is written as a blockquote list. With `--yaml` it becomes standard YAML frontmatter:

```yaml
---
title: "Article title"
account: "Account name"
date: "2026-11-23 07:56"
source: "https://mp.weixin.qq.com/s/xxxxx"
description: "Summary"
---
```

**Unstable network**

Exponential backoff retry is built in (1/2/4/8 seconds, capped at 30) along with explicit CAPTCHA detection. On an "environment error" it raises `CaptchaError` immediately instead of wasting retry time. You can tune it:

```bash
wechat-token-saver URL --timeout 60 --retries 5
```

**JSON output** (for scripting)

```bash
wechat-token-saver URL --json
```

**Default output path**

Use an environment variable so you don't have to type `-o` every time:

```bash
export WECHAT_TOKEN_SAVER_OUTPUT=~/Documents/wechat_articles
# Windows PowerShell:
# $env:WECHAT_TOKEN_SAVER_OUTPUT = "$HOME\Documents\wechat_articles"
```

### Output structure

```
articles/
├── _index.json                     # index of all articles
└── Article title/
    ├── Article title.md            # body text, image links localized
    ├── images/
    │   ├── img_001.jpg
    │   └── ...
    ├── image_manifest.md           # image manifest (ranked by information density)
    └── meta.json                   # title / account / time / chars / image count
```

**What the image manifest looks like**

| File | Size | KB | Context | Advice | Score |
|---|---|---|---|---|---|
| images/img_005.jpg | 863x1004 | 93.9 | …Gemini's best position is next to Claude… | **must-read** | 70 |
| images/img_009.jpg | 783x495 | 35.4 | …GPT closes the loop at the end… | **must-read** | 40 |
| images/img_003.jpg | 346x373 | 87.4 | …GPT has the highest information density… | skip | 5 |

The ranking is not based on pixel count alone. It combines:

- Whether nearby text contains cues like "below", "flow", "structure"
- Aspect ratio (near-square often means a diagram; very wide often means a table or timeline)
- Image area

**Purpose**: let the AI read only the images worth reading, instead of dumping dozens of decorative images into context.

### Python API

```python
from wechat_token_saver import fetch_article, ArticleFetcher

# Simplest
result = fetch_article("https://mp.weixin.qq.com/s/xxxxx")
print(result.title, result.account, result.char_count)

# Reuse config for batch fetching
fetcher = ArticleFetcher("./articles", timeout=30, retries=3)
results = fetcher.fetch_many([
    "https://mp.weixin.qq.com/s/aaa",
    "https://mp.weixin.qq.com/s/bbb",
])
for r in results:
    for image in r.images:
        if image.priority == "优先读":
            print(image.file, image.context)
```

### Notes

**The link must come from WeChat itself**:

- Short link `https://mp.weixin.qq.com/s/xxxxx` ✅
- Full long link (with `__biz&mid&idx&sn&chksm`) ✅
- Hand-built URLs missing `chksm` ❌ will return an "environment error"

To get it: open the article → top-right "···" → **Copy link**.

**Network**: the program connects to `mp.weixin.qq.com` directly from your machine — no third-party server. Image downloads carry a `Referer` header to bypass hotlink protection.

**Rate**: the tool sleeps 1 second between fetches. Don't lower it when batching, or you risk triggering rate limits.

### Common errors

| Message | Cause | Fix |
|---|---|---|
| "Environment error" | Link rate-limited or incomplete parameters | Re-copy via WeChat "Copy link"; retry after a few minutes |
| Too few images | Some hotlink protection | Normal — core images are usually kept |
| `captcha` errors | High request rate or flagged UA | Slow down; don't use a minimal UA |

### Development

```bash
pip install -e ".[dev]"
pytest
```

### Usage terms

Personal use, learning and derivative development are welcome. For commercial products or public-facing services, please:

- Keep the original author credit and a link to this project
- Let me know (GitHub Issue or private message is fine)
- If it saved you money, a star is the best support

This is a courtesy request, not a legal term. Rights and limitations are defined in LICENSE.

### License

MIT — commercial use and modification allowed, provided the copyright notice and license text are retained.

### Disclaimer

This tool is for personal archiving and study only. Respect original authors' copyright; do not use it for bulk scraping or commercial redistribution of others' content.
