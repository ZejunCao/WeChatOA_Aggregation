# -*- coding: utf-8 -*-
"""微信公众号「图片消息」（小绿书 / item_show_type 8、10 等）解析与预览。"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import quote

from lxml import etree

from src.utils.wechat_body import is_allowed_wechat_image_url
from src.utils.wechat_preview import (
    _ARTICLE_HEADER_CSS,
    _PREVIEW_AI_CSS,
    _PREVIEW_SURFACE_CSS,
    _build_ai_insights_html,
    _escape_html_text,
    _extract_page_meta,
)

_PREVIEW_PICTURE_MARKER = "preview-picture-v3"
_PICTURE_SHOW_TYPES = frozenset({8, 10})


def parse_item_show_type(html: str) -> int:
    """从页面脚本读取展示类型（普通图文多为 0）。"""
    m = re.search(r"item_show_type\s*:\s*['\"]?(\d+)", html)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except ValueError:
        return 0


def is_picture_message_html(html: str) -> bool:
    if not html or not html.strip():
        return False
    show_type = parse_item_show_type(html)
    has_picture_list = bool(
        re.search(r"picture_page_info_list\s*[:=]\s*\[", html)
    )
    has_picture_urls = bool(
        re.search(r"cdn_url\s*:\s*['\"]https://mmbiz\.qpic\.cn/", html)
    )
    has_stream_marker = (
        "js_row_immersive_stream" in html
        or "wx_stream_article" in html
        or "immersive_stream" in html
    )
    tree = etree.HTML(html, parser=etree.HTMLParser(encoding="utf-8"))
    rich_text_len = 0
    if tree is not None:
        rich_nodes = tree.xpath('//*[contains(@class, "rich_media_content")]')
        if rich_nodes:
            rich_text_len = len("".join(rich_nodes[0].itertext()).strip())
    # 仅当命中图片流数据结构时，才认定为图片消息，避免普通图文被 item_show_type 误伤。
    if (
        has_picture_list
        and has_picture_urls
        and (has_stream_marker or show_type in _PICTURE_SHOW_TYPES)
        and rich_text_len < 120
    ):
        return True
    return False


def _picture_url_key(url: str) -> str:
    m = re.search(r"/mmbiz_[^/]+/([^/]+)/", url)
    if m:
        return m.group(1)
    return url.split("?")[0]


def _picture_url_rank(url: str) -> int:
    score = len(url)
    if "/sz_mmbiz" in url or "/sz_" in url:
        score += 10_000
    return score


def decode_wechat_escaped_text(text: str) -> str:
    """解码 og:description 等字段里的 \\x26lt; 形式转义。"""
    if not text:
        return ""
    s = text.strip()

    def _hex_byte(m: re.Match[str]) -> str:
        return chr(int(m.group(1), 16))

    s = re.sub(r"\\x([0-9a-fA-F]{2})", _hex_byte, s)
    return unescape(s)


def normalize_wechat_meta_digest(digest: str) -> str:
    """图片消息描述：话题标签拉平为纯文本，供入库与 FTS。"""
    s = decode_wechat_escaped_text(digest)
    if not s:
        return ""
    if "<" not in s:
        return s
    tree = etree.HTML(
        f'<div id="wx-digest-root">{s}</div>',
        parser=etree.HTMLParser(encoding="utf-8"),
    )
    if tree is None:
        return re.sub(r"<[^>]+>", " ", s).strip()
    tags: list[str] = []
    for node in tree.xpath('//a[contains(@class, "wx_topic_link")]'):
        t = "".join(node.itertext()).strip()
        if t:
            tags.append(t)
    if tags:
        return " ".join(tags)
    root = tree.xpath('//*[@id="wx-digest-root"]')
    if root:
        return "".join(root[0].itertext()).strip()
    return re.sub(r"<[^>]+>", " ", s).strip()


def format_picture_digest_html(digest: str) -> str:
    """预览区展示话题标签（已解码，非原始转义串）。"""
    s = decode_wechat_escaped_text(digest)
    if not s:
        return ""
    if "<" not in s:
        hash_tags = [t for t in re.split(r"\s+", s) if t.startswith("#")]
        if len(hash_tags) >= 2:
            chips = "".join(
                f'<span class="wx-picture-tag">{_escape_html_text(t)}</span>'
                for t in hash_tags
            )
            return f'<div class="wx-picture-tags">{chips}</div>'
        return f'<div class="wx-picture-digest">{_escape_html_text(s)}</div>'
    tree = etree.HTML(
        f'<div id="wx-digest-root">{s}</div>',
        parser=etree.HTMLParser(encoding="utf-8"),
    )
    if tree is None:
        return f'<div class="wx-picture-digest">{_escape_html_text(s)}</div>'
    tags: list[str] = []
    for node in tree.xpath('//a[contains(@class, "wx_topic_link")]'):
        t = "".join(node.itertext()).strip()
        if t:
            tags.append(t)
    if not tags:
        plain = ""
        root = tree.xpath('//*[@id="wx-digest-root"]')
        if root:
            plain = "".join(root[0].itertext()).strip()
        if not plain:
            plain = re.sub(r"<[^>]+>", " ", s).strip()
        return f'<div class="wx-picture-digest">{_escape_html_text(plain)}</div>'
    chips = "".join(
        f'<span class="wx-picture-tag">{_escape_html_text(t)}</span>' for t in tags
    )
    return f'<div class="wx-picture-tags">{chips}</div>'


def _extract_picture_urls_from_lists(html: str) -> list[str]:
    """从各 picture_page_info_list 块取每页首图（页面内嵌数据，可能不全）。"""
    ordered: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"picture_page_info_list\s*[:=]\s*\[", html):
        chunk = html[m.end() : m.end() + 8000]
        url_m = re.search(
            r"cdn_url\s*:\s*['\"](https://mmbiz\.qpic\.cn/[^'\"]+)['\"]",
            chunk,
        )
        if not url_m:
            continue
        url = url_m.group(1).replace("&amp;", "&").strip()
        if not is_allowed_wechat_image_url(url):
            continue
        key = _picture_url_key(url)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(url)
    return ordered


def extract_picture_urls(html: str) -> list[str]:
    """
    从图片消息页提取按页排序的图片 URL（去重并优先高清）。
    """
    from_lists = _extract_picture_urls_from_lists(html)
    if len(from_lists) >= 3:
        return from_lists

    raw = re.findall(
        r"cdn_url\s*:\s*['\"](https://mmbiz\.qpic\.cn/[^'\"]+)['\"]",
        html,
    )
    if not raw:
        raw = re.findall(
            r"data-src\s*=\s*['\"](https://mmbiz\.qpic\.cn/[^'\"]+)['\"]",
            html,
        )
    ordered_keys: list[str] = []
    best: dict[str, str] = {}
    for url in raw:
        url = url.replace("&amp;", "&").strip()
        if not is_allowed_wechat_image_url(url):
            continue
        key = _picture_url_key(url)
        if key not in best:
            ordered_keys.append(key)
            best[key] = url
            continue
        if _picture_url_rank(url) > _picture_url_rank(best[key]):
            best[key] = url
    return [best[k] for k in ordered_keys]


def _proxy_image_url(url: str) -> str:
    if is_allowed_wechat_image_url(url):
        return f"/api/wechat-image?url={quote(url, safe='')}"
    return url


_PICTURE_CAROUSEL_CSS = """
/* preview-picture-v1 */
.wx-picture-preview{max-width:667px;margin:0 auto}
.wx-picture-header{padding:4px 18px 8px}
.wx-picture-hint{
  display:flex;align-items:center;justify-content:center;gap:6px;
  margin:0 0 12px;font-size:13px;color:rgba(0,0,0,.45);
}
.wx-picture-hint svg{flex-shrink:0;opacity:.7}
.wx-picture-stage{
  position:relative;
  margin:0 12px 10px;
  border-radius:12px;
  overflow:hidden;
  background:#fdfbf7;
  touch-action:none;
}
.wx-picture-track{
  display:flex;
  overflow-x:auto;
  overflow-y:hidden;
  scroll-snap-type:x mandatory;
  -webkit-overflow-scrolling:touch;
  scrollbar-width:none;
  touch-action:pan-x;
}
.wx-picture-track::-webkit-scrollbar{display:none}
.wx-picture-slide{
  flex:0 0 100%;
  scroll-snap-align:start;
  scroll-snap-stop:normal;
  display:flex;
  align-items:center;
  justify-content:center;
  min-height:min(72vh,520px);
  max-height:78vh;
  background:#fdfbf7;
}
.wx-picture-slide img{
  display:block;
  width:100%;
  max-height:78vh;
  object-fit:contain;
  user-select:none;
  -webkit-user-drag:none;
  cursor:zoom-in;
}
.wx-picture-nav{
  position:absolute;top:50%;transform:translateY(-50%);
  width:36px;height:36px;border:none;border-radius:50%;
  background:rgba(0,0,0,.45);color:#fff;line-height:1;
  cursor:pointer;z-index:5;pointer-events:auto;
  display:flex;align-items:center;justify-content:center;
  backdrop-filter:blur(4px);
  padding:0;
}
.wx-picture-nav:disabled{opacity:.25;cursor:default}
.wx-picture-nav-icon{width:18px;height:18px;stroke:currentColor;stroke-width:2.5;fill:none}
.wx-picture-nav--prev{left:8px}
.wx-picture-nav--next{right:8px}
.wx-picture-counter{
  text-align:center;font-size:13px;color:rgba(0,0,0,.5);
  margin:4px 0 10px;
}
.wx-picture-thumbs{
  display:flex;gap:8px;padding:0 14px 16px;
  overflow-x:auto;-webkit-overflow-scrolling:touch;
  scrollbar-width:none;
}
.wx-picture-thumbs::-webkit-scrollbar{display:none}
.wx-picture-thumb{
  flex:0 0 auto;width:52px;height:70px;border-radius:6px;
  overflow:hidden;border:2px solid transparent;cursor:pointer;
  opacity:.55;transition:opacity .15s,border-color .15s;
  background:#e8e4de;padding:0;pointer-events:auto;
}
.wx-picture-tags{
  display:flex;flex-wrap:wrap;gap:8px;
  margin:0 18px 14px;
}
.wx-picture-tag{
  display:inline-flex;align-items:center;
  padding:4px 10px;font-size:13px;line-height:1.35;
  color:#576b95;background:rgba(87,107,149,.1);
  border-radius:999px;
}
.wx-picture-thumb.is-active{
  opacity:1;border-color:#07c160;
}
.wx-picture-thumb img{
  width:100%;height:100%;object-fit:cover;display:block;
}
.wx-picture-digest{
  margin:0 18px 16px;font-size:14px;line-height:1.65;
  color:rgba(0,0,0,.72);white-space:pre-wrap;word-break:break-word;
}
.wx-picture-slide img{cursor:zoom-in}
"""

_PICTURE_CAROUSEL_JS = """
(function(){
  var track = document.getElementById('wx-picture-track');
  if (!track) return;
  var thumbStrip = document.getElementById('wx-picture-thumbs');
  var slides = track.querySelectorAll('.wx-picture-slide');
  var thumbs = document.querySelectorAll('.wx-picture-thumb');
  var counter = document.getElementById('wx-picture-counter');
  var btnPrev = document.getElementById('wx-picture-prev');
  var btnNext = document.getElementById('wx-picture-next');
  var total = slides.length;
  if (!total) return;
  var activeIndex = 0;
  var suppressImageClickUntil = 0;
  var dragStartX = 0;
  var dragStartY = 0;
  var dragging = false;

  function pageScrollY(){
    return window.scrollY
      || document.documentElement.scrollTop
      || document.body.scrollTop
      || 0;
  }

  function restorePageScroll(y){
    window.scrollTo(0, y);
  }

  function indexFromScroll(){
    var w = track.clientWidth || 1;
    return Math.max(0, Math.min(total - 1, Math.round(track.scrollLeft / w)));
  }

  function scrollThumbStrip(i){
    if (!thumbStrip || !thumbs[i]) return;
    var t = thumbs[i];
    var target = t.offsetLeft - (thumbStrip.clientWidth - t.offsetWidth) / 2;
    thumbStrip.scrollTo({
      left: Math.max(0, target),
      behavior: 'smooth'
    });
  }

  function setActive(i, opts){
    opts = opts || {};
    i = Math.max(0, Math.min(total - 1, i));
    activeIndex = i;
    if (counter) counter.textContent = (i + 1) + ' / ' + total;
    thumbs.forEach(function(t, j){
      t.classList.toggle('is-active', j === i);
    });
    if (opts.scrollThumb) scrollThumbStrip(i);
    if (btnPrev) btnPrev.disabled = i <= 0;
    if (btnNext) btnNext.disabled = i >= total - 1;
  }

  function scrollTo(i){
    var keepY = pageScrollY();
    var w = track.clientWidth || 1;
    i = Math.max(0, Math.min(total - 1, i));
    track.scrollTo({left: i * w, behavior: 'smooth'});
    setActive(i, {scrollThumb: true});
    requestAnimationFrame(function(){ restorePageScroll(keepY); });
    window.setTimeout(function(){ restorePageScroll(keepY); }, 280);
  }

  function preventFocusScroll(el){
    el.addEventListener('mousedown', function(e){ e.preventDefault(); });
  }

  function onPointerStart(x, y){
    dragStartX = x;
    dragStartY = y;
    dragging = false;
  }

  function onPointerMove(x, y){
    if (dragging) return;
    if (Math.abs(x - dragStartX) > 9 || Math.abs(y - dragStartY) > 9) {
      dragging = true;
      suppressImageClickUntil = Date.now() + 260;
    }
  }

  track.addEventListener('touchstart', function(e){
    var t = e.touches && e.touches[0];
    if (!t) return;
    onPointerStart(t.clientX, t.clientY);
  }, {passive:true});
  track.addEventListener('touchmove', function(e){
    var t = e.touches && e.touches[0];
    if (!t) return;
    onPointerMove(t.clientX, t.clientY);
  }, {passive:true});
  track.addEventListener('touchend', function(){
    if (dragging) suppressImageClickUntil = Date.now() + 260;
    dragging = false;
  }, {passive:true});
  track.addEventListener('mousedown', function(e){
    onPointerStart(e.clientX, e.clientY);
  });
  track.addEventListener('mousemove', function(e){
    onPointerMove(e.clientX, e.clientY);
  });
  track.addEventListener('mouseup', function(){
    if (dragging) suppressImageClickUntil = Date.now() + 260;
    dragging = false;
  });

  track.addEventListener('scroll', function(){
    window.requestAnimationFrame(function(){
      setActive(indexFromScroll());
    });
  }, {passive:true});

  if (btnPrev) {
    preventFocusScroll(btnPrev);
    btnPrev.addEventListener('click', function(e){
      e.preventDefault();
      e.stopPropagation();
      scrollTo(activeIndex - 1);
    });
  }
  if (btnNext) {
    preventFocusScroll(btnNext);
    btnNext.addEventListener('click', function(e){
      e.preventDefault();
      e.stopPropagation();
      scrollTo(activeIndex + 1);
    });
  }
  thumbs.forEach(function(t){
    preventFocusScroll(t);
    t.addEventListener('click', function(e){
      e.preventDefault();
      e.stopPropagation();
      var idx = parseInt(t.getAttribute('data-index') || '0', 10);
      scrollTo(idx);
    });
  });

  function normalizeLightboxSrc(raw){
    var src = (raw || '').trim();
    if (!src) return '';
    if (/^https?:\\/\\//i.test(src)) return src;
    if (src.charAt(0) === '/' && src.indexOf('/api/wechat-image') === 0) return src;
    return '';
  }
  function openParentLightbox(src){
    src = normalizeLightboxSrc(src);
    if (!src) return;
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({ type: 'wx-preview-img-open', src: src }, '*');
      }
    } catch (e) {}
  }

  slides.forEach(function(s){
    var img = s.querySelector('img');
    if (!img) return;
    img.addEventListener('click', function(e){
      if (Date.now() < suppressImageClickUntil) return;
      e.preventDefault();
      e.stopPropagation();
      openParentLightbox(img.getAttribute('src') || '');
    });
  });

  setActive(0);
})();
"""


def build_picture_preview_document(
    raw_html: str,
    title: str = "",
    *,
    ai_summary: str | None = None,
    ai_tags: list[str] | None = None,
    fallback_pub_time: str = "",
    fallback_pub_unix: int | None = None,
    digest: str = "",
) -> str:
    """构建图片消息横滑预览 HTML（iframe srcdoc）。"""
    images = extract_picture_urls(raw_html)
    if not images:
        return ""

    page_meta = _extract_page_meta(raw_html)
    pub = page_meta.get("pub_time_display") or ""
    if not pub and fallback_pub_unix:
        from src.utils.wechat_preview import _format_wechat_pub_time_unix

        try:
            pub = _format_wechat_pub_time_unix(int(fallback_pub_unix))
        except (ValueError, OSError, OverflowError):
            pub = ""
    if not pub and fallback_pub_time:
        from src.utils.wechat_preview import _format_wechat_pub_time_str

        pub = _format_wechat_pub_time_str(fallback_pub_time) or ""

    safe_title = _escape_html_text(title or "图片消息")
    ai_html = _build_ai_insights_html(ai_summary, ai_tags)
    digest_html = format_picture_digest_html(digest or "")

    slides_html: list[str] = []
    thumbs_html: list[str] = []
    for i, url in enumerate(images):
        proxied = _proxy_image_url(url)
        slides_html.append(
            f'<div class="wx-picture-slide" data-index="{i}">'
            f'<img src="{_escape_html_text(proxied)}" alt="第{i + 1}页" loading="'
            f'{"eager" if i < 2 else "lazy"}" decoding="async" referrerpolicy="no-referrer">'
            f"</div>"
        )
        thumbs_html.append(
            f'<button type="button" class="wx-picture-thumb{" is-active" if i == 0 else ""}" '
            f'data-index="{i}" aria-label="第{i + 1}页">'
            f'<img src="{_escape_html_text(proxied)}" alt="" loading="lazy"></button>'
        )

    meta_bits: list[str] = []
    if pub:
        meta_bits.append(
            f'<em id="publish_time" class="rich_media_meta rich_media_meta_text">{_escape_html_text(pub)}</em>'
        )
    ip = page_meta.get("ip_wording", "").strip()
    if ip:
        meta_bits.append(
            f'<span id="js_ip_wording_wrp" class="rich_media_meta rich_media_meta_text">'
            f'<span id="js_ip_wording">{_escape_html_text(ip)}</span></span>'
        )
    meta_row = ""
    if meta_bits:
        meta_row = (
            '<div id="meta_content" class="rich_media_meta_list">'
            + "".join(meta_bits)
            + "</div>"
        )

    hint_svg = (
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <!-- {_PREVIEW_PICTURE_MARKER} -->
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
  <meta name="color-scheme" content="light">
  <title>{safe_title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif; }}
    {_PREVIEW_SURFACE_CSS}
    {_PREVIEW_AI_CSS}
    {_ARTICLE_HEADER_CSS}
    {_PICTURE_CAROUSEL_CSS}
  </style>
</head>
<body data-weui-theme="light" data-wx-preview-kind="picture">
<div id="js_article" class="wx-picture-preview">
  <div class="wx-picture-header">
    <h1 id="activity-name" class="rich_media_title">{safe_title}</h1>
    {meta_row}
    {ai_html}
    <p class="wx-picture-hint">{hint_svg}左右滑动切换图片</p>
  </div>
  {digest_html}
  <div class="wx-picture-stage">
    <button type="button" class="wx-picture-nav wx-picture-nav--prev" id="wx-picture-prev" aria-label="上一张">
      <svg class="wx-picture-nav-icon" viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></svg>
    </button>
    <div class="wx-picture-track" id="wx-picture-track">
      {"".join(slides_html)}
    </div>
    <button type="button" class="wx-picture-nav wx-picture-nav--next" id="wx-picture-next" aria-label="下一张">
      <svg class="wx-picture-nav-icon" viewBox="0 0 24 24"><path d="M9 18l6-6-6-6"/></svg>
    </button>
  </div>
  <div class="wx-picture-counter" id="wx-picture-counter">1 / {len(images)}</div>
  <div class="wx-picture-thumbs" id="wx-picture-thumbs">
    {"".join(thumbs_html)}
  </div>
</div>
<script>{_PICTURE_CAROUSEL_JS}</script>
</body>
</html>"""


def is_picture_preview_document(html: str | None) -> bool:
    if not html or not html.strip():
        return False
    return _PREVIEW_PICTURE_MARKER in html
