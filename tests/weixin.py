import json
import requests
from bs4 import BeautifulSoup

BASE = "http://118.195.150.71:11235"


def crawl_wechat_article(url: str):
    payload = {
        "urls": [url],
        "browser_config": {
            "type": "BrowserConfig",
            "params": {
                "headless": True,
                "java_script_enabled": True,
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "viewport": {
                    "type": "dict",
                    "value": {"width": 1280, "height": 720}
                },
                "headers": {
                    "type": "dict",
                    "value": {
                        "Referer": "https://mp.weixin.qq.com/",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
                    }
                },
                "text_mode": True,
                "light_mode": True,
                "enable_stealth": True,
                "extra_args": [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                    "--hide-scrollbars",
                    "--blink-settings=imagesEnabled=false"
                ]
            }
        },
        "crawler_config": {
            "type": "CrawlerRunConfig",
            "params": {
                "cache_mode": "bypass",
                "locale": "zh-CN",
                "wait_until": "networkidle",
                "page_timeout": 30000,
                "wait_for": "css:h1.rich_media_title",
                "wait_for_timeout": 30000,
                "delay_before_return_html": 2.0,
                "simulate_user": True,
                "override_navigator": True,
                "remove_overlay_elements": True,
                "js_code_before_wait": """
                    (() => {
                        const nodes = Array.from(document.querySelectorAll('a, button, div, span'));
                        const target = nodes.find(el => {
                            const txt = (el.innerText || el.textContent || '').trim();
                            return txt === '去验证' || txt.includes('去验证');
                        });
                        if (target) target.click();
                    })();
                """
            }
        }
    }

    try:
        resp = requests.post(f"{BASE}/crawl", json=payload, timeout=90)
        # 这里不要直接 raise，先把服务端正文打出来方便排查
        if not resp.ok:
            return {
                "title": None,
                "markdown": "",
                "extracted_content": {
                    "success": False,
                    "status_code": resp.status_code,
                    "error": resp.text
                }
            }

        data = resp.json()
        results = data.get("results") or []
        if not results:
            return {
                "title": None,
                "markdown": "",
                "extracted_content": {
                    "success": False,
                    "error": "results 为空",
                    "raw": data
                }
            }

        first = results[0]
        if not first.get("success", False):
            return {
                "title": None,
                "markdown": "",
                "extracted_content": {
                    "success": False,
                    "error": first.get("error_message") or first,
                    "raw": first
                }
            }

        html = first.get("html") or ""
        soup = BeautifulSoup(html, "html.parser")

        title_node = soup.select_one("h1.rich_media_title")
        content_node = soup.select_one("div.rich_media_content")

        title = title_node.get_text("\n", strip=True) if title_node else None
        content = content_node.get_text("\n", strip=True) if content_node else ""

        markdown = f"## {title}\n\n{content}" if title else content

        return {
            "title": title,
            "markdown": markdown,
            "extracted_content": {
                "url": url,
                "filter": "raw",
                "query": "",
                "cache": "0",
                "markdown": markdown,
                "success": True
            }
        }

    except Exception as e:
        return {
            "title": None,
            "markdown": "",
            "extracted_content": {
                "success": False,
                "error": str(e)
            }
        }


if __name__ == "__main__":
    url = "https://mp.weixin.qq.com/s/-hhmx_7jnAJ1th2f56uoBw"
    res = crawl_wechat_article(url)
    print(json.dumps(res, ensure_ascii=False, indent=2))