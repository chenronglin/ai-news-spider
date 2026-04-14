"""
mhtml_to_markdown.py
将 MHTML 文件一键转换为 Markdown 文件。

用法:
    python mhtml_to_markdown.py <mhtml_file_path> <output_md_name>

示例:
    python mhtml_to_markdown.py page.mhtml output.md
"""

import argparse
import logging
import sys
import os
import re
import mimetypes
import uuid
import base64
import quopri
import html
import hashlib
import shutil
import time
from urllib.parse import urlparse, unquote
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, List, Union

# ── 依赖检查 ────────────────────────────────────────────────────────────────
try:
    from bs4 import BeautifulSoup
except ImportError:
    print("[ERROR] 缺少依赖: beautifulsoup4\n请执行: pip install beautifulsoup4")
    sys.exit(1)

try:
    import markdownify
except ImportError:
    print("[ERROR] 缺少依赖: markdownify\n请执行: pip install markdownify")
    sys.exit(1)

# ── 日志配置 ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s]: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────────────────────────────
DEFAULT_BUFFER_SIZE = 8192
MIN_BUFFER_SIZE = 1024
MAX_BUFFER_SIZE = 1024 * 1024


# ── 内嵌精简版 MHTMLExtractor ────────────────────────────────────────────────
@dataclass
class ExtractionStats:
    total_parts: int = 0
    html_files: int = 0
    skipped_files: int = 0
    total_size: int = 0
    extraction_time: float = 0.0


class MHTMLExtractor:
    """精简版 MHTML 提取器，仅保留内存输出功能。"""

    def __init__(self, mhtml_path: Union[str, Path], buffer_size: int = DEFAULT_BUFFER_SIZE) -> None:
        self.mhtml_path = Path(mhtml_path).resolve()
        if not self.mhtml_path.exists():
            raise FileNotFoundError(f"MHTML 文件不存在: {self.mhtml_path}")

        # 自动优化 buffer_size
        try:
            file_size = self.mhtml_path.stat().st_size
            buffer_size = min(max(file_size // 100, MIN_BUFFER_SIZE), MAX_BUFFER_SIZE)
        except OSError:
            pass
        self.buffer_size = buffer_size

        self.boundary: Optional[str] = None
        self.extracted_count: int = 0
        self.url_mapping: Dict[str, str] = {}
        self.stats = ExtractionStats()
        # { filename: { 'content_type': str, 'decoded_body': bytes|str } }
        self.extracted_contents: Dict[str, Dict[str, Union[str, bytes]]] = {}

    # ── 静态辅助 ──────────────────────────────────────────────────────────────
    @staticmethod
    def _read_boundary(buf: str) -> Optional[str]:
        for pattern in [r'boundary="([^"]+)"', r'boundary=([^;\s]+)']:
            m = re.search(pattern, buf, re.IGNORECASE)
            if m:
                b = m.group(1).strip()
                if b:
                    return b
        return None

    @staticmethod
    def _decode_body(encoding: Optional[str], body: str) -> Union[str, bytes]:
        if not encoding:
            return body
        encoding = encoding.lower().strip()
        try:
            if encoding == "base64":
                return base64.b64decode(re.sub(r'\s+', '', body))
            elif encoding == "quoted-printable":
                return quopri.decodestring(body.encode()).decode('utf-8', errors='replace')
            else:
                return body
        except Exception as e:
            logger.warning(f"解码失败 ({encoding}): {e}")
            return body

    def _extract_filename(self, headers: str, content_type: str) -> str:
        loc_match = re.search(r"Content-Location:\s*([^\r\n]+)", headers, re.IGNORECASE)
        ext = mimetypes.guess_extension(content_type) or ""
        if loc_match:
            location = loc_match.group(1).strip()
            parsed = urlparse(location)
            base = os.path.basename(unquote(parsed.path)) or parsed.netloc
            base = re.sub(r'[<>:"/\\|?*]', '_', base) or "unnamed"
            url_hash = hashlib.md5(location.encode()).hexdigest()
            return f"{base}_{url_hash}{ext}"
        return f"{uuid.uuid4()}{ext}"

    # ── 处理单个 part ─────────────────────────────────────────────────────────
    def _process_part(self, part: str) -> None:
        try:
            sep = "\r\n\r\n" if "\r\n\r\n" in part else "\n\n"
            if sep not in part:
                return
            headers, body = part.split(sep, 1)

            ct_match = re.search(r"Content-Type:\s*([^\r\n;]+)", headers, re.IGNORECASE)
            if not ct_match:
                self.stats.skipped_files += 1
                return

            content_type = ct_match.group(1).strip().lower()

            # 跳过图片
            if "image" in content_type:
                self.stats.skipped_files += 1
                return

            enc_match = re.search(r"Content-Transfer-Encoding:\s*([^\r\n]+)", headers, re.IGNORECASE)
            encoding = enc_match.group(1).strip() if enc_match else None
            decoded_body = self._decode_body(encoding, body)

            filename = self._extract_filename(headers, content_type)

            loc_match = re.search(r"Content-Location:\s*([^\r\n]+)", headers, re.IGNORECASE)
            if loc_match:
                self.url_mapping[loc_match.group(1).strip()] = filename

            cid_match = re.search(r"Content-ID:\s*<([^>]+)>", headers, re.IGNORECASE)
            if cid_match:
                self.url_mapping["cid:" + cid_match.group(1)] = filename

            self.extracted_contents[filename] = {
                'content_type': content_type,
                'decoded_body': decoded_body,
            }

            self.stats.total_parts += 1
            size = len(decoded_body.encode('utf-8') if isinstance(decoded_body, str) else decoded_body)
            self.stats.total_size += size
            if "html" in content_type:
                self.stats.html_files += 1

        except Exception as e:
            logger.warning(f"处理 part 失败: {e}")
            self.stats.skipped_files += 1

    # ── 主提取入口 ────────────────────────────────────────────────────────────
    def extract(self) -> ExtractionStats:
        t0 = time.time()
        chunks: List[str] = []

        with open(self.mhtml_path, "r", encoding="utf-8", errors="replace") as f:
            while True:
                chunk = f.read(self.buffer_size)
                if not chunk:
                    break
                chunks.append(chunk)

                if not self.boundary:
                    self.boundary = self._read_boundary("".join(chunks))

                if self.boundary:
                    joined = "".join(chunks)
                    parts = joined.split("--" + self.boundary)
                    chunks = [parts[-1]]
                    for part in parts[:-1]:
                        if self.extracted_count > 0:
                            self._process_part(part.strip())
                        self.extracted_count += 1

        if chunks and self.boundary:
            remaining = "".join(chunks).strip()
            if remaining and remaining != "--":
                self._process_part(remaining)

        self.stats.extraction_time = time.time() - t0
        return self.stats


# ── HTML → Markdown 转换 ──────────────────────────────────────────────────────
def html_to_markdown(html_content: Union[str, bytes]) -> str:
    """将 HTML 内容转换为 Markdown 字符串。"""
    if isinstance(html_content, bytes):
        html_content = html_content.decode("utf-8", errors="replace")

    # BeautifulSoup 清洗：去除 <script>/<style>，保留正文结构
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "noscript", "head"]):
        tag.decompose()

    clean_html = str(soup)

    md = markdownify.markdownify(
        clean_html,
        heading_style=markdownify.ATX,   # # H1 风格
        bullets="-",
        strip=["img"],                    # 不输出图片
        newline_style="backslash",
    )

    # 清理多余空行（连续超过 2 行空行压缩为 2 行）
    md = re.sub(r'\n{3,}', '\n\n', md)
    return md.strip()


# ── 主逻辑 ───────────────────────────────────────────────────────────────────
def convert(mhtml_path: str, output_md: str) -> None:
    logger.info(f"读取 MHTML: {mhtml_path}")
    extractor = MHTMLExtractor(mhtml_path)
    stats = extractor.extract()
    logger.info(f"提取完成: {stats.total_parts} 个 part，"
                f"其中 HTML {stats.html_files} 个，"
                f"跳过 {stats.skipped_files} 个，"
                f"耗时 {stats.extraction_time:.2f}s")

    if stats.html_files == 0:
        logger.error("未找到任何 HTML 内容，请确认 MHTML 文件是否有效。")
        sys.exit(1)

    # 合并所有 HTML（通常主页面是第一个 HTML part）
    html_parts: List[str] = []
    for filename, info in extractor.extracted_contents.items():
        if "html" in info["content_type"]:
            md_chunk = html_to_markdown(info["decoded_body"])
            if md_chunk:
                # 如果有多个 HTML part，用分隔线隔开
                if html_parts:
                    html_parts.append("\n\n---\n\n")
                html_parts.append(md_chunk)

    if not html_parts:
        logger.error("HTML 内容为空，转换中止。")
        sys.exit(1)

    final_md = "\n".join(html_parts)

    output_path = Path(output_md)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final_md, encoding="utf-8")
    logger.info(f"Markdown 已保存到: {output_path} ({len(final_md):,} 字符)")


# ── CLI 入口 ─────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="将 MHTML 文件转换为 Markdown（忽略图片）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python mhtml_to_markdown.py page.mhtml output.md
  python mhtml_to_markdown.py ~/Downloads/article.mhtml ~/docs/article.md
        """,
    )
    parser.add_argument("mhtml_file_path", help="MHTML 源文件路径")
    parser.add_argument("output_md_name",  help="输出 Markdown 文件路径（含文件名）")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出详细日志")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        convert(args.mhtml_file_path, args.output_md_name)
    except FileNotFoundError as e:
        logger.error(e)
        sys.exit(1)
    except Exception as e:
        logger.error(f"意外错误: {e}")
        if args.verbose:
            import traceback; traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()