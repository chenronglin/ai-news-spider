import asyncio
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

ARTICLE_URL = "https://lxy.shzu.edu.cn/2026/0412/c528a230917/page.htm"


async def main():
    async with AsyncWebCrawler() as crawler:
        article = await crawler.arun(
            ARTICLE_URL,
            config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_for="css:.wp_pdf_player",
                page_timeout=60000,
                verbose=False,
                log_console=False,
            ),
        )

        soup = BeautifulSoup(article.html, "html.parser")
        iframe = soup.select_one("iframe.wp_pdf_player")
        if not iframe:
            raise RuntimeError("没有找到 PDF 预览 iframe")

        viewer_url = urljoin(ARTICLE_URL, iframe["src"])

        pdf_view = await crawler.arun(
            viewer_url,
            config=CrawlerRunConfig(
                css_selector=".pdfViewer",
                cache_mode=CacheMode.BYPASS,
                wait_for="css:#viewer",
                delay_before_return_html=5.0,
                page_timeout=90000,
                verbose=False,
                log_console=False,
            ),
        )

    pdf_text = str(pdf_view.markdown)
    print("viewer_url =", viewer_url)
    print()
    print(pdf_text[:3000])


asyncio.run(main())
