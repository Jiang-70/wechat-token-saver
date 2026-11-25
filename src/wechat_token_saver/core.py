"""核心抓取逻辑：无第三方 AI 工具依赖，可独立使用。"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

__version__ = "1.1.0"

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class FetchError(RuntimeError):
    """抓取失败（网络、参数错误等）。"""


class CaptchaError(FetchError):
    """微信返回验证码或「环境异常」拦截页。"""


@dataclass
class ImageInfo:
    file: str
    width: int
    height: int
    kb: float
    context: str
    score: int

    @property
    def priority(self) -> str:
        if self.score >= 40:
            return "优先读"
        if self.score >= 15:
            return "可选"
        return "可跳过"


@dataclass
class ArticleResult:
    title: str
    account: str
    publish_time: str
    url: str
    body: str
    md_path: Path
    article_dir: Path
    images: list[ImageInfo] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return len(self.body)

    @property
    def image_count(self) -> int:
        return len(self.images)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "account": self.account,
            "publish_time": self.publish_time,
            "url": self.url,
            "md": str(self.md_path),
            "dir": str(self.article_dir),
            "chars": self.char_count,
            "images": self.image_count,
        }


class ArticleFetcher:
    """公众号文章抓取器。

    用法:
        fetcher = ArticleFetcher(output_dir="./articles")
        result = fetcher.fetch("https://mp.weixin.qq.com/s/xxxxx")
        print(result.title, result.char_count)
    """

    MIN_HTML_BYTES = 30000
    MIN_IMAGE_BYTES = 3000
    MAX_BACKOFF = 30  # 退避上限，避免长重试链拖太久
    CAPTCHA_MARKERS = ("captcha", "环境异常", "完成验证后即可继续访问", "去验证")
    HINT_WORDS = (
        "下图", "上图", "如下", "图 ", "图1", "图 1", "流程", "架构", "结构",
        "表格", "对比", "流程图", "如图", "见图",
    )
    DECOR_WORDS = ("配图", "截图", "如下是", "网络", "来源")

    def __init__(
        self,
        output_dir: str | os.PathLike = "articles",
        *,
        user_agent: str = DEFAULT_UA,
        timeout: int = 30,
        retries: int = 3,
        download_images: bool = True,
        yaml_frontmatter: bool = False,
    ) -> None:
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = retries
        self.download_images = download_images
        self.yaml_frontmatter = yaml_frontmatter

    # ---------- 网络 ----------

    def _get(
        self,
        url: str,
        *,
        referer: Optional[str] = None,
        min_bytes: int = 0,
        retries: Optional[int] = None,
    ) -> bytes:
        """带指数退避重试的 GET。UA 太精简会触发微信风控，必须用完整浏览器串。"""
        retries = self.retries if retries is None else retries
        last: Exception = FetchError("抓取失败")

        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Connection": "close",
                })
                if referer:
                    req.add_header("Referer", referer)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = resp.read()
                    final_url = resp.geturl()

                # 验证码/环境异常单独识别，给出可操作的错误信息
                if self._is_blocked(final_url, data):
                    raise CaptchaError(
                        "微信返回验证码或「环境异常」。请确认链接来自微信「复制链接」"
                        "（短链或完整长链），并降低抓取频率后重试。"
                    )
                if len(data) < min_bytes:
                    raise FetchError(f"返回内容过短（{len(data)} 字节），疑似被拦截")
                return data
            except CaptchaError as exc:
                last = exc
                # 验证码靠重试解决不了，不要浪费退避时间
                break
            except (urllib.error.URLError, OSError, FetchError) as exc:
                last = FetchError(f"网络错误: {exc}") if not isinstance(exc, FetchError) else exc

            if attempt < retries - 1:
                # 指数退避: 1, 2, 4, 8 秒 ... 上限 MAX_BACKOFF
                delay = min(2 ** attempt, self.MAX_BACKOFF)
                time.sleep(delay)
        raise last

    @classmethod
    def _is_blocked(cls, final_url: str, data: bytes) -> bool:
        """判断是否被微信风控拦截。只看 URL 与页面前 4KB，避免误伤正文里的关键词。"""
        if any(marker in final_url.lower() for marker in cls.CAPTCHA_MARKERS):
            return True
        head = data[:4096].decode("utf-8", errors="ignore")
        return any(marker in head for marker in cls.CAPTCHA_MARKERS if marker != "captcha")


    # ---------- 解析 ----------

    @staticmethod
    def _decode(raw: bytes) -> str:
        for enc in ("utf-8", "gbk", "gb18030"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="ignore")

    @staticmethod
    def _meta(soup: BeautifulSoup) -> dict:
        def get(name: str) -> str:
            el = soup.find("meta", attrs={"name": name}) or soup.find(
                "meta", attrs={"property": name}
            )
            return el.get("content", "").strip() if el and el.get("content") else ""

        meta = {
            "title": get("og:title") or get("twitter:title"),
            "desc": get("og:description") or get("description"),
            "account": "",
            "publish_time": "",
        }
        for sel in ("#js_name", ".profile_nickname", "#profileBt a"):
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                meta["account"] = el.get_text(strip=True)
                break

        html = str(soup)
        ts = None
        patterns = (
            r'publish_time(?:%22|"|\\")?\s*[:=]\s*(?:"|%22|\\")?(\d{10})',
            r'var\s+(?:ct|create_time)\s*=\s*[\"\\\'](?:"|%22)?(\d{10})',
            r'"publish_time"\s*:\s*"(\d{10})"',
        )
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                ts = int(match.group(1))
                break
        if ts:
            meta["publish_time"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        return meta

    @staticmethod
    def _safe_name(value: str, maxlen: int = 60) -> str:
        value = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", (value or "untitled").strip())
        return (value[:maxlen] or "untitled").strip()

    def _download_images(
        self, soup: BeautifulSoup, img_dir: Path, article_url: str
    ) -> list[tuple[str, int]]:
        """下载配图并把 img 的 src 改成本地相对路径。"""
        img_dir.mkdir(parents=True, exist_ok=True)
        saved: list[tuple[str, int]] = []

        content = soup.select_one("#js_content") or soup.select_one(".rich_media_content")
        scope = content or soup
        for i, img in enumerate(scope.find_all("img"), 1):
            src = img.get("data-src") or img.get("src") or ""
            if not src or src.startswith("data:"):
                continue
            name = f"img_{i:03d}.jpg"
            try:
                data = self._get(
                    src, referer=article_url, min_bytes=0, retries=1
                )
            except FetchError:
                continue
            if len(data) < self.MIN_IMAGE_BYTES:
                continue
            (img_dir / name).write_bytes(data)
            img["src"] = f"images/{name}"
            saved.append((name, len(data)))

        for selector, prefix in (
            ("#js_profile_qrcode img", "qrcode"),
            (".profile_avatar img", "avatar"),
        ):
            el = soup.select_one(selector)
            if not el:
                continue
            src = el.get("data-src") or el.get("src") or ""
            if not src.startswith("http"):
                continue
            try:
                data = self._get(src, referer=article_url, min_bytes=0, retries=1)
            except FetchError:
                continue
            if len(data) > 1000:
                (img_dir / f"{prefix}.jpg").write_bytes(data)
                saved.append((f"{prefix}.jpg", len(data)))
        return saved

    @staticmethod
    def _to_markdown(content_el) -> str:
        """正文 DOM -> Markdown，保留图片与表格。"""
        if content_el is None:
            return ""

        for table in list(content_el.find_all("table")):
            rows = []
            for tr in table.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                lines = [
                    "| " + " | ".join(rows[0]) + " |",
                    "|" + "---|" * width,
                ]
                lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
                table.replace_with("\n\n" + "\n".join(lines) + "\n\n")
            else:
                table.decompose()

        soup = BeautifulSoup(content_el.decode_contents(), "lxml")
        for img in soup.find_all("img"):
            src = img.get("src") or ""
            if not src:
                img.decompose()
                continue
            alt = (img.get("alt") or "").strip()
            img.replace_with(f"\n\n![{alt}]({src})\n\n")
        for br in soup.find_all("br"):
            br.replace_with("\n")
        for block in soup.find_all(["p", "section", "div"]):
            block.append("\n")

        text = soup.get_text()
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _image_manifest(self, article_dir: Path, md_path: Path) -> list[ImageInfo]:
        """按信息密度给配图排序，供 AI 按需读图。"""
        try:
            from PIL import Image
        except ImportError:
            return []

        lines = md_path.read_text(encoding="utf-8").splitlines()
        infos: list[ImageInfo] = []

        for path in sorted((article_dir / "images").glob("*.jpg")):
            rel = f"images/{path.name}"
            try:
                with Image.open(path) as im:
                    width, height = im.size
            except Exception:
                width = height = 0

            idx = next((i for i, line in enumerate(lines) if rel in line), -1)
            before = " ".join(line.strip() for line in lines[max(0, idx - 4):idx] if line.strip())
            after = " ".join(line.strip() for line in lines[idx + 1:idx + 4] if line.strip())
            ctx = (before[-70:] + (" | " if before and after else "") + after[:70]).strip()

            score = 0
            if any(word in ctx for word in self.HINT_WORDS):
                score += 40
            if any(word in ctx for word in self.DECOR_WORDS):
                score -= 25
            ratio = width / height if height else 0
            if 0.75 <= ratio <= 1.35:
                score += 20
            elif ratio > 1.6:
                score += 15
            if width * height > 500000:
                score += 10
            if width * height < 250000:
                score -= 15

            infos.append(ImageInfo(
                file=rel,
                width=width,
                height=height,
                kb=round(path.stat().st_size / 1024, 1),
                context=ctx,
                score=score,
            ))

        infos.sort(key=lambda item: -item.score)
        manifest_path = article_dir / "image_manifest.md"
        lines_out = [
            "# 图片清单", "",
            "按信息密度排序。优先读的图大概率含结构/数据信息；小图多为装饰或二维码。",
            "", "| 文件 | 尺寸 | KB | 上下文 | 建议 | 分值 |",
            "|---|---|---|---|---|---|",
        ]
        for info in infos:
            lines_out.append(
                f"| {info.file} | {info.width}x{info.height} | {info.kb} | "
                f"{info.context[:46]} | {info.priority} | {info.score} |"
            )
        manifest_path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
        return infos

    # ---------- 主流程 ----------

    @staticmethod
    def _yaml_quote(value: str) -> str:
        """YAML 标量转义：含特殊字符时用双引号包裹。"""
        value = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        return f'"{value}"' if value else '""'

    def _build_header(self, title: str, meta: dict, url: str) -> list[str]:
        """生成 Markdown 头部：默认引用块格式，可选 YAML frontmatter。"""
        desc = meta.get("desc", "").replace("\\x0d", "").replace("\\x0a", " ").strip()

        if self.yaml_frontmatter:
            lines = ["---"]
            lines.append(f"title: {self._yaml_quote(title)}")
            lines.append(f"account: {self._yaml_quote(meta.get('account') or '未知')}")
            if meta.get("publish_time"):
                lines.append(f"date: {self._yaml_quote(meta['publish_time'])}")
            lines.append(f"source: {self._yaml_quote(url)}")
            if desc:
                lines.append(f"description: {self._yaml_quote(desc)}")
            lines += ["---", "", f"# {title}", ""]
            return lines

        lines = [f"# {title}", "", f"- 来源公众号: {meta.get('account') or '未知'}"]
        if meta.get("publish_time"):
            lines.append(f"- 发布时间: {meta['publish_time']}")
        lines.append(f"- 原文链接: {url}")
        if desc:
            lines.append(f"- 摘要: {desc}")
        lines += ["", "---", ""]
        return lines

    def fetch(self, url: str) -> ArticleResult:
        """抓取单篇文章并落盘，返回结构化结果。"""
        raw = self._get(url, min_bytes=self.MIN_HTML_BYTES)
        html = self._decode(raw)

        if "环境异常" in html or len(raw) < self.MIN_HTML_BYTES:
            raise FetchError(
                "微信返回「环境异常」：链接可能被风控，或不是微信「复制链接」生成的。"
                "短链 /s/xxxx 或完整长链均可。"
            )

        soup = BeautifulSoup(html, "lxml")
        meta = self._meta(soup)
        title = meta["title"]
        if not title:
            heading = soup.find("h1")
            title = heading.get_text(strip=True) if heading else "untitled"

        article_dir = self.output_dir / self._safe_name(title)
        img_dir = article_dir / "images"
        article_dir.mkdir(parents=True, exist_ok=True)

        content_el = soup.select_one("#js_content") or soup.select_one(".rich_media_content")
        if self.download_images:
            self._download_images(soup, img_dir, url)
        body = self._to_markdown(content_el)

        header = self._build_header(title, meta, url)

        md_path = article_dir / f"{self._safe_name(title)}.md"
        md_path.write_text("\n".join(header) + body + "\n", encoding="utf-8")

        infos = self._image_manifest(article_dir, md_path) if self.download_images else []

        result = ArticleResult(
            title=title,
            account=meta["account"],
            publish_time=meta["publish_time"],
            url=url,
            body=body,
            md_path=md_path,
            article_dir=article_dir,
            images=infos,
        )
        (article_dir / "meta.json").write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result

    def fetch_many(self, urls: list[str]) -> list[ArticleResult]:
        """批量抓取，失败的不中断整体流程。"""
        results = []
        for url in urls:
            try:
                results.append(self.fetch(url))
            except FetchError as exc:
                print(f"[失败] {url[:80]} -> {exc}")
            time.sleep(1)
        self._write_index(results)
        return results

    def _write_index(self, results: list[ArticleResult]) -> Path:
        index_path = self.output_dir / "_index.json"
        old = []
        if index_path.exists():
            try:
                old = json.loads(index_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                old = []
        merged, seen = [], set()
        for item in [r.to_dict() for r in results] + old:
            title = item.get("title")
            if title and title not in seen:
                seen.add(title)
                merged.append(item)
        index_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return index_path


def fetch_article(
    url: str,
    output_dir: str | os.PathLike = "articles",
    **kwargs,
) -> ArticleResult:
    """便捷函数：抓一篇文章。"""
    return ArticleFetcher(output_dir, **kwargs).fetch(url)
