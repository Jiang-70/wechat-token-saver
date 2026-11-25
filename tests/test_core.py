"""离线测试：不访问网络，用构造的 HTML 验证解析逻辑。"""
import pytest
from bs4 import BeautifulSoup

from wechat_token_saver.core import ArticleFetcher


SAMPLE_HTML = """
<html><head>
<meta property="og:title" content="测试文章标题">
<meta property="og:description" content="这是一段摘要">
</head><body>
<a id="js_name">测试公众号</a>
<div id="publish_time">2026-11-24 20:00</div>
<div id="js_content">
  <p>第一段正文。</p>
  <p>第二段正文，含<b>加粗</b>。</p>
  <table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>
  <p><img data-src="https://example.com/img.jpg" alt="测试图"></p>
</div>
</body></html>
"""


def test_meta_extraction():
    soup = BeautifulSoup(SAMPLE_HTML, "lxml")
    meta = ArticleFetcher._meta(soup)
    assert meta["title"] == "测试文章标题"
    assert meta["account"] == "测试公众号"
    assert meta["desc"] == "这是一段摘要"


def test_markdown_conversion():
    soup = BeautifulSoup(SAMPLE_HTML, "lxml")
    content = soup.select_one("#js_content")
    for img in content.find_all("img"):
        img["src"] = img.get("data-src", "")
    md = ArticleFetcher._to_markdown(content)
    assert "第一段正文" in md
    assert "加粗" in md
    assert "| A | B |" in md
    assert "![测试图](https://example.com/img.jpg)" in md


def test_safe_name():
    assert ArticleFetcher._safe_name("a/b:c*d") == "a_b_c_d"
    assert ArticleFetcher._safe_name("") == "untitled"


def test_fetch_error_type():
    from wechat_token_saver.core import FetchError
    with pytest.raises(FetchError):
        raise FetchError("test")


def test_version():
    from wechat_token_saver import __version__
    assert __version__ == "1.1.0"


def test_captcha_detection():
    """验证码页要被识别，且不能被正文里的关键词误伤。"""
    assert ArticleFetcher._is_blocked(
        "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha?poc_token=xxx", b""
    )
    assert ArticleFetcher._is_blocked(
        "https://mp.weixin.qq.com/s/xxx",
        "环境异常，完成验证后即可继续访问".encode(),
    )
    # 正常正文里提到"验证码"不应被误判
    assert not ArticleFetcher._is_blocked(
        "https://mp.weixin.qq.com/s/xxx",
        "<html>这篇文章讲验证码的原理与实现</html>".encode(),
    )


def test_captcha_error_type():
    from wechat_token_saver.core import CaptchaError, FetchError
    assert issubclass(CaptchaError, FetchError)


def test_yaml_header():
    fetcher = ArticleFetcher(yaml_frontmatter=True)
    meta = {
        "title": "测试:文章",
        "account": "号",
        "publish_time": "2026-11-24 20:00",
        "desc": "一段摘要",
    }
    header = fetcher._build_header(meta["title"], meta, "https://example.com/a")
    assert header[0] == "---"
    assert 'title: "测试:文章"' in header
    assert 'description: "一段摘要"' in header
    assert "---" in header
    assert f"# {meta['title']}" in header


def test_plain_header_is_default():
    fetcher = ArticleFetcher()
    meta = {"title": "标题", "account": "号", "publish_time": "", "desc": ""}
    header = fetcher._build_header("标题", meta, "https://example.com/a")
    assert header[0] == "# 标题"
    assert "- 来源公众号: 号" in header
    assert header[0] != "---"


def test_exponential_backoff_constant():
    """退避上限存在且为正，1/2/4 序列不超过上限。"""
    f = ArticleFetcher()
    assert f.MAX_BACKOFF > 0
    assert min(2 ** 0, f.MAX_BACKOFF) == 1
    assert min(2 ** 1, f.MAX_BACKOFF) == 2
    assert min(2 ** 2, f.MAX_BACKOFF) == 4
