"""微信公众号文章抓取与归档。

公开 API:
    fetch_article(url, output_dir, ...) -> ArticleResult
    ArticleFetcher 类支持复用会话配置
"""
from .core import (
    ArticleFetcher,
    ArticleResult,
    FetchError,
    CaptchaError,
    fetch_article,
    __version__,
)

__all__ = [
    "ArticleFetcher",
    "ArticleResult",
    "FetchError",
    "CaptchaError",
    "fetch_article",
    "__version__",
]
