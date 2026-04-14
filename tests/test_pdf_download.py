import asyncio
import re
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from bs4 import BeautifulSoup
import httpx
import pymupdf  # pip install pymupdf

"""
直接下载 PDF 解析（推荐）从 viewer URL 里提取真实 PDF 地址，用 pymupdf 解析全文
"""

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

ARTICLE_URL = "https://yz.shmtu.edu.cn/2026/0326/c8927a289142/page.htm"


def extract_pdf_url_from_viewer(viewer_url: str, base_url: str) -> str | None:
    """从 PDF.js viewer URL 中提取真实 PDF 文件地址"""
    parsed = urlparse(viewer_url)
    params = parse_qs(parsed.query)

    # 常见参数名：file, pdfurl, src
    for key in ("file", "pdfurl", "src", "url"):
        if key in params:
            pdf_path = unquote(params[key][0])
            return urljoin(base_url, pdf_path)

    # 兜底：正则匹配
    match = re.search(r'[?&](?:file|pdfurl|src|url)=([^&]+)', viewer_url)
    if match:
        return urljoin(base_url, unquote(match.group(1)))

    return None


async def get_pdf_text_via_download(pdf_url: str, base_url: str) -> str:
    """直接下载 PDF 并用 pymupdf 提取全文"""
    base_origin = "{0.scheme}://{0.netloc}".format(urlparse(base_url))

    headers = {
        "Referer": base_url,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        resp = await client.get(pdf_url, headers=headers)
        resp.raise_for_status()
        pdf_bytes = resp.content

    # 用 pymupdf 提取所有页面文本
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages_text = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if text:
            pages_text.append(f"=== 第 {page_num} 页 ===\n{text}")

    doc.close()
    return "\n\n".join(pages_text)


async def main():
    async with AsyncWebCrawler() as crawler:
        # Step 1: 抓取文章页，找到 PDF iframe
        article = await crawler.arun(
            ARTICLE_URL,
            config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_for="css:.wp_pdf_player",
                page_timeout=60000,
            ),
        )

        soup = BeautifulSoup(article.html, "html.parser")
        iframe = soup.select_one("iframe.wp_pdf_player")
        if not iframe:
            raise RuntimeError("没有找到 PDF 预览 iframe")

        viewer_url = urljoin(ARTICLE_URL, iframe["src"])
        print("viewer_url =", viewer_url)

        # Step 2: 从 viewer URL 提取真实 PDF 地址
        pdf_url = extract_pdf_url_from_viewer(viewer_url, ARTICLE_URL)
        if not pdf_url:
            raise RuntimeError(f"无法从 viewer URL 解析出 PDF 地址: {viewer_url}")

        print("pdf_url =", pdf_url)

        # Step 3: 直接下载并解析 PDF 全文
        full_text = await get_pdf_text_via_download(pdf_url, ARTICLE_URL)

    print("\n" + "=" * 60)
    print(full_text)


asyncio.run(main())