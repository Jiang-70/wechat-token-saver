---
name: wechat-token-saver
description: 读取微信公众号文章并节省 token。当用户发来 mp.weixin.qq.com 链接，或说「抓这篇公众号文章」「读这篇公众号」「把公众号存下来」「读优先读图片」时使用。把文章抓成 Markdown 正文 + 本地配图 + 图片优先级清单，并只让模型读真正有信息量的图（数据图、流程图、结构图），跳过装饰图、头像、二维码。支持短链与完整长链、批量多篇。
---

# 公众号文章读取器（省 token 版）

用户给出微信公众号链接并希望阅读时，按本流程执行。

## 核心原则

- 抓取本身在本地完成，**真正的成本是"读正文"和"读图"进上下文**。
- **图片比正文更贵**。不要无脑读完所有配图，按清单的信息密度挑选。
- 用户没说"读所有图"时，**只读标「优先读」的图**。

## 第 0 步：确认工具可用

先检查命令是否存在：

```bash
wechat-token-saver --version
```

如果提示找不到命令，说明还没安装。执行安装：

```bash
pip install wechat-token-saver
```

安装后重试 `--version`。若仍失败，告诉用户需要本机有 Python 3.10+，并让其安装 Python。

## 第 1 步：抓取文章

```bash
wechat-token-saver "<链接>" -o ./wechat_articles
```

多篇可一次传入：

```bash
wechat-token-saver "<链接1>" "<链接2>" -o ./wechat_articles
```

常用选项：

| 选项 | 用途 |
|---|---|
| `--yaml` | 输出 YAML frontmatter（方便接入 Obsidian 等知识库） |
| `--no-images` | 只要正文，不下载配图 |
| `--list` | 列出已抓取的文章 |
| `--json` | 以 JSON 输出，便于脚本处理 |

也可以自定义环境变量 `WECHAT_TOKEN_SAVER_OUTPUT` 指定默认输出目录。

## 第 2 步：读图片清单

每篇文章目录下会生成 `image_manifest.md`，按信息密度排序：

| 建议 | 分值 | 处理 |
|---|---|---|
| **优先读** | ≥40 | 读。大概率是数据图/流程图/结构图 |
| 可选 | 15–39 | 视用户要求 |
| 可跳过 | <15 | 不读。多为装饰图、头像、二维码 |

「上下文」列是图片在正文里的相邻文字，用来判断该不该读。

## 第 3 步：读正文与选中的图

- 读 `<标题>.md` 得到正文（图片引用已本地化为 `images/xxx.jpg`）。
- 用阅读图片的能力读「优先读」的图。读图时说明要提取什么，例如："列出这张数据图的坐标轴、图例和全部数值"。
- 若正文出现「如下图」「流程」「结构」「如表」但内容缺失，必须读对应图片。

## 第 4 步：汇报

说清三件事：文章标题与来源、核心结论、读了哪几张图以及读出了什么。

## 常见问题

| 症状 | 处理 |
|---|---|
| 返回「环境异常」 | 链接不是微信「复制链接」生成的，或缺 `chksm`。请用户重新复制；等几分钟再试 |
| 配图偏少 | 部分图片被防盗链拦截属正常，核心图一般都在 |
| 找不到命令 | 先 `pip install wechat-token-saver`；确认 Python 3.10+ |
| 验证码错误 | 抓取频率过高，降低频率后重试 |

## 产物结构

```
wechat_articles/
├── _index.json
└── <文章标题>/
    ├── <文章标题>.md
    ├── images/
    ├── image_manifest.md
    └── meta.json
```

## 项目信息

- GitHub: https://github.com/Jiang-70/wechat-token-saver
- PyPI: https://pypi.org/project/wechat-token-saver/
- License: MIT
