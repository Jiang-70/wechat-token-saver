"""命令行入口：python -m wechat_token_saver <url> [options]"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .core import ArticleFetcher, FetchError, __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wechat-token-saver",
        description="把微信公众号文章抓成 Markdown + 本地配图 + 图片清单",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  wechat-token-saver https://mp.weixin.qq.com/s/xxxxx
  wechat-token-saver URL1 URL2 -o ./my_articles
  wechat-token-saver --from-file links.txt
  wechat-token-saver URL --yaml          # YAML frontmatter
  wechat-token-saver URL --no-images     # 只要正文
  wechat-token-saver --list

环境变量:
  WECHAT_TOKEN_SAVER_OUTPUT   默认输出目录（默认 ./articles）
  WECHAT_TOKEN_SAVER_NO_IMG   设为 1 则跳过配图下载
""",
    )
    parser.add_argument("urls", nargs="*", help="公众号文章链接（短链或完整长链）")
    parser.add_argument(
        "-o", "--output", default=None,
        help="输出目录（默认取 WECHAT_TOKEN_SAVER_OUTPUT 或 ./articles）",
    )
    parser.add_argument(
        "--from-file", metavar="TXT",
        help="从文本文件读取链接，每行一个，# 开头为注释",
    )
    parser.add_argument("--list", action="store_true", help="列出已抓取的文章")
    parser.add_argument("--no-images", action="store_true", help="不下载配图")
    parser.add_argument("--yaml", action="store_true", help="用 YAML frontmatter 输出元数据")
    parser.add_argument("--timeout", type=int, default=30, help="网络超时秒数（默认 30）")
    parser.add_argument("--retries", type=int, default=3, help="重试次数（默认 3）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    parser.add_argument("-V", "--version", action="version", version=f"wechat-token-saver {__version__}")
    return parser


def default_output() -> Path:
    env = os.environ.get("WECHAT_TOKEN_SAVER_OUTPUT")
    return Path(env).expanduser() if env else Path("./articles")


def resolve_urls(args: argparse.Namespace) -> list[str]:
    urls = list(args.urls)
    if args.from_file:
        path = Path(args.from_file).expanduser()
        if not path.exists():
            print(f"找不到文件: {path}", file=sys.stderr)
            sys.exit(2)
        urls += [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    return urls


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output = Path(args.output).expanduser() if args.output else default_output()
    no_images = args.no_images or os.environ.get("WECHAT_TOKEN_SAVER_NO_IMG") == "1"
    fetcher = ArticleFetcher(
        output,
        timeout=args.timeout,
        retries=args.retries,
        download_images=not no_images,
        yaml_frontmatter=args.yaml,
    )

    if args.list:
        found = []
        if output.exists():
            for entry in sorted(output.iterdir()):
                meta = entry / "meta.json"
                if entry.is_dir() and meta.exists():
                    try:
                        found.append(json.loads(meta.read_text(encoding="utf-8")))
                    except (ValueError, OSError):
                        pass
        if args.json:
            print(json.dumps(found, ensure_ascii=False, indent=2))
        else:
            if not found:
                print("还没有抓取任何文章")
                return 0
            print(f"已有 {len(found)} 篇:\n")
            for i, item in enumerate(found, 1):
                print(f"{i:2d}. {item.get('title', '?')}")
                print(f"    {item.get('chars', 0)}字 / {item.get('images', 0)}图  "
                      f"{item.get('account', '')}  {item.get('publish_time', '')}")
                print(f"    {item.get('md', '')}")
        return 0

    urls = resolve_urls(args)
    if not urls:
        parser.print_help()
        return 1

    results = []
    for url in urls:
        print(f"抓取: {url[:90]}", file=sys.stderr)
        try:
            result = fetcher.fetch(url)
        except FetchError as exc:
            print(f"  [失败] {exc}", file=sys.stderr)
            continue
        results.append(result)
        print(f"  {result.title}  ({result.char_count}字, {result.image_count}图)", file=sys.stderr)
        print(f"    正文: {result.md_path}", file=sys.stderr)
        print(f"    清单: {result.article_dir / 'image_manifest.md'}", file=sys.stderr)

    fetcher._write_index(results)

    if args.json:
        print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
    else:
        print(f"\n完成 {len(results)}/{len(urls)} 篇", file=sys.stderr)
        print(f"输出目录: {output}", file=sys.stderr)
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
