"""
app.py — MHTML → Markdown Web 转换器
运行方式: streamlit run app.py
依赖: pip install streamlit beautifulsoup4 markdownify
"""

import re
import os
import mimetypes
import uuid
import base64
import quopri
import hashlib
import time
import io
import logging
from urllib.parse import urlparse, unquote
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Union

import streamlit as st

try:
    from bs4 import BeautifulSoup
except ImportError:
    st.error("缺少依赖：请执行 `pip install beautifulsoup4`")
    st.stop()

try:
    import markdownify
except ImportError:
    st.error("缺少依赖：请执行 `pip install markdownify`")
    st.stop()

# ── 常量 ─────────────────────────────────────────────────────────────────────
DEFAULT_BUFFER_SIZE = 8192
MIN_BUFFER_SIZE = 1024
MAX_BUFFER_SIZE = 1024 * 1024
logging.basicConfig(level=logging.WARNING)


# ── 数据类 ────────────────────────────────────────────────────────────────────
@dataclass
class ExtractionStats:
    total_parts: int = 0
    html_files: int = 0
    skipped_files: int = 0
    total_size: int = 0
    extraction_time: float = 0.0


# ── 精简版 MHTMLExtractor（内存模式）────────────────────────────────────────
class MHTMLExtractor:
    def __init__(self, content: str, buffer_size: int = DEFAULT_BUFFER_SIZE) -> None:
        self.content = content
        self.buffer_size = min(max(buffer_size, MIN_BUFFER_SIZE), MAX_BUFFER_SIZE)
        self.boundary: Optional[str] = None
        self.extracted_count: int = 0
        self.url_mapping: Dict[str, str] = {}
        self.stats = ExtractionStats()
        self.extracted_contents: Dict[str, Dict[str, Union[str, bytes]]] = {}

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
        enc = encoding.lower().strip()
        try:
            if enc == "base64":
                return base64.b64decode(re.sub(r'\s+', '', body))
            elif enc == "quoted-printable":
                return quopri.decodestring(body.encode()).decode('utf-8', errors='replace')
            else:
                return body
        except Exception:
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
        except Exception:
            self.stats.skipped_files += 1

    def extract(self) -> ExtractionStats:
        t0 = time.time()
        chunks: List[str] = []
        stream = io.StringIO(self.content)

        while True:
            chunk = stream.read(self.buffer_size)
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


# ── HTML → Markdown ───────────────────────────────────────────────────────────
def html_to_markdown(html_content: Union[str, bytes]) -> str:
    if isinstance(html_content, bytes):
        html_content = html_content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "noscript", "head"]):
        tag.decompose()
    md = markdownify.markdownify(
        str(soup),
        heading_style=markdownify.ATX,
        bullets="-",
        strip=["img"],
        newline_style="backslash",
    )
    return re.sub(r'\n{3,}', '\n\n', md).strip()


def convert_mhtml_to_markdown(file_content: str) -> tuple[str, ExtractionStats]:
    extractor = MHTMLExtractor(file_content)
    stats = extractor.extract()

    if stats.html_files == 0:
        raise ValueError("未找到任何 HTML 内容，请确认 MHTML 文件是否有效。")

    parts_md: List[str] = []
    for info in extractor.extracted_contents.values():
        if "html" in info["content_type"]:
            chunk = html_to_markdown(info["decoded_body"])
            if chunk:
                if parts_md:
                    parts_md.append("\n\n---\n\n")
                parts_md.append(chunk)

    if not parts_md:
        raise ValueError("HTML 内容为空，转换失败。")

    return "".join(parts_md), stats


# ── 页面样式 ──────────────────────────────────────────────────────────────────
def inject_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');

    :root {
        --ink:       #1a1714;
        --paper:     #f7f4ef;
        --cream:     #ede9e1;
        --accent:    #c84b2f;
        --accent2:   #2d6a4f;
        --muted:     #8a8078;
        --border:    #d5cfc4;
    }

    html, body, [data-testid="stAppViewContainer"] {
        background: var(--paper) !important;
        font-family: 'DM Sans', sans-serif;
        color: var(--ink);
    }

    [data-testid="stHeader"] { background: transparent !important; }
    [data-testid="stSidebar"] { display: none; }

    /* ── 主容器 ── */
    .main .block-container {
        max-width: 860px !important;
        padding: 3rem 2rem 5rem !important;
    }

    /* ── 顶部标题区 ── */
    .hero {
        margin-bottom: 3rem;
        padding-bottom: 2rem;
        border-bottom: 2px solid var(--ink);
    }
    .hero-label {
        font-family: 'DM Mono', monospace;
        font-size: 0.7rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--accent);
        margin-bottom: 0.6rem;
    }
    .hero-title {
        font-family: 'Instrument Serif', serif;
        font-size: 3.2rem;
        line-height: 1.1;
        color: var(--ink);
        margin: 0 0 0.5rem;
    }
    .hero-sub {
        font-size: 0.95rem;
        color: var(--muted);
        font-weight: 300;
    }

    /* ── 上传区 ── */
    [data-testid="stFileUploader"] {
        border: 2px dashed var(--border) !important;
        border-radius: 4px !important;
        background: var(--cream) !important;
        padding: 1.5rem !important;
        transition: border-color .2s;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: var(--accent) !important;
    }
    [data-testid="stFileUploader"] label {
        font-family: 'DM Mono', monospace !important;
        font-size: 0.78rem !important;
        letter-spacing: 0.08em !important;
        color: var(--muted) !important;
    }

    /* ── 统计卡片 ── */
    .stat-row {
        display: flex;
        gap: 1rem;
        margin: 1.5rem 0;
        flex-wrap: wrap;
    }
    .stat-card {
        flex: 1;
        min-width: 110px;
        background: var(--cream);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 0.8rem 1rem;
        text-align: center;
    }
    .stat-num {
        font-family: 'Instrument Serif', serif;
        font-size: 1.9rem;
        color: var(--accent);
        line-height: 1;
    }
    .stat-label {
        font-family: 'DM Mono', monospace;
        font-size: 0.65rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--muted);
        margin-top: 0.2rem;
    }

    /* ── Markdown 预览容器 ── */
    .md-preview-wrap {
        background: white;
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 2rem 2.5rem;
        font-family: 'DM Sans', sans-serif;
        font-size: 0.92rem;
        line-height: 1.75;
        color: var(--ink);
        max-height: 520px;
        overflow-y: auto;
    }
    .md-preview-wrap h1, .md-preview-wrap h2, .md-preview-wrap h3 {
        font-family: 'Instrument Serif', serif;
        color: var(--ink);
        margin-top: 1.4em;
    }
    .md-preview-wrap code {
        font-family: 'DM Mono', monospace;
        font-size: 0.82rem;
        background: var(--cream);
        padding: 0.1em 0.4em;
        border-radius: 3px;
    }
    .md-preview-wrap a { color: var(--accent2); }
    .md-preview-wrap hr { border-color: var(--border); }

    /* ── 节标题 ── */
    .section-label {
        font-family: 'DM Mono', monospace;
        font-size: 0.7rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 0.6rem;
    }

    /* ── 下载按钮 ── */
    [data-testid="stDownloadButton"] > button {
        background: var(--ink) !important;
        color: var(--paper) !important;
        border: none !important;
        border-radius: 3px !important;
        font-family: 'DM Mono', monospace !important;
        font-size: 0.78rem !important;
        letter-spacing: 0.1em !important;
        padding: 0.6rem 1.4rem !important;
        transition: background .2s !important;
    }
    [data-testid="stDownloadButton"] > button:hover {
        background: var(--accent) !important;
    }

    /* ── 错误/警告 ── */
    [data-testid="stAlert"] {
        border-radius: 4px !important;
        font-size: 0.88rem !important;
    }

    /* ── 进度条 ── */
    [data-testid="stProgress"] > div > div {
        background: var(--accent) !important;
    }

    /* ── 隐藏 streamlit 品牌 ── */
    #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)


def render_stat_cards(stats: ExtractionStats, char_count: int):
    size_kb = round(stats.total_size / 1024, 1)
    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card">
            <div class="stat-num">{stats.html_files}</div>
            <div class="stat-label">HTML 段落</div>
        </div>
        <div class="stat-card">
            <div class="stat-num">{stats.total_parts}</div>
            <div class="stat-label">总 Parts</div>
        </div>
        <div class="stat-card">
            <div class="stat-num">{size_kb}K</div>
            <div class="stat-label">原始大小</div>
        </div>
        <div class="stat-card">
            <div class="stat-num">{char_count:,}</div>
            <div class="stat-label">MD 字符数</div>
        </div>
        <div class="stat-card">
            <div class="stat-num">{stats.extraction_time:.2f}s</div>
            <div class="stat-label">处理耗时</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── 主应用 ────────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="MHTML → Markdown",
        page_icon="📄",
        layout="centered",
    )
    inject_styles()

    # 顶部标题
    st.markdown("""
    <div class="hero">
        <div class="hero-label">Document Converter</div>
        <div class="hero-title">MHTML → Markdown</div>
        <div class="hero-sub">上传 .mhtml 文件，一键提取为干净的 Markdown 文本，图片自动忽略。</div>
    </div>
    """, unsafe_allow_html=True)

    # 上传区
    st.markdown('<div class="section-label">选择文件</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        label="拖拽或点击上传 MHTML 文件",
        type=["mhtml", "mht"],
        label_visibility="collapsed",
    )

    if uploaded is None:
        st.markdown("""
        <div style="margin-top:3rem;text-align:center;color:var(--muted);font-size:0.85rem;font-family:'DM Mono',monospace;letter-spacing:.06em;">
            支持 .mhtml / .mht 格式 · 图片内容将被自动过滤
        </div>
        """, unsafe_allow_html=True)
        return

    # 读取并转换
    with st.spinner("正在解析 MHTML 并转换…"):
        progress = st.progress(0)
        try:
            raw = uploaded.read().decode("utf-8", errors="replace")
            progress.progress(30)

            md_text, stats = convert_mhtml_to_markdown(raw)
            progress.progress(100)
            time.sleep(0.15)
            progress.empty()

        except ValueError as e:
            progress.empty()
            st.error(f"转换失败：{e}")
            return
        except Exception as e:
            progress.empty()
            st.error(f"意外错误：{e}")
            return

    # 统计卡片
    render_stat_cards(stats, len(md_text))

    st.divider()

    # 预览
    col_l, col_r = st.columns([1, 1])
    with col_l:
        st.markdown('<div class="section-label">Markdown 预览</div>', unsafe_allow_html=True)
    with col_r:
        stem = Path(uploaded.name).stem
        st.download_button(
            label="⬇  下载 .md 文件",
            data=md_text.encode("utf-8"),
            file_name=f"{stem}.md",
            mime="text/markdown",
        )

    # 使用 st.code 做可滚动预览（保留换行）
    st.code(md_text[:8000] + ("\n\n…（内容过长，已截断预览，完整内容请下载）" if len(md_text) > 8000 else ""),
            language="markdown")


if __name__ == "__main__":
    main()