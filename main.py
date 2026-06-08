"""多引擎搜索插件 for AstrBot

功能：
  1. /websearch [关键词] — 手动触发搜索
  2. web_search — LLM函数工具，AI在对话中可**主动调用**搜索

支持的搜索引擎（通过插件配置界面选择）：
  - sogou    搜狗搜索（中文友好，推荐）
  - google   Google 搜索
  - bing     Bing 搜索

用法：
  把本目录复制到 AstrBot 的 data/plugin/ 目录
"""

import re
import urllib.request
import urllib.error
import urllib.parse
import html as html_module
from typing import Optional, List, Dict

from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent

# ═══════════════════════════════════════════
# 搜索引擎定义
# ═══════════════════════════════════════════
SEARCH_ENGINES: Dict[str, dict] = {
    "sogou": {
        "name": "搜狗搜索",
        "url_pattern": "https://www.sogou.com/web?query={query}",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        "parse": "sogou",
    },
    "google": {
        "name": "Google 搜索",
        "url_pattern": "https://www.google.com/search?q={query}&num={num}&hl=zh-CN",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        "parse": "google",
    },
    "bing": {
        "name": "Bing 搜索",
        "url_pattern": "https://www.bing.com/search?q={query}&count={num}",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        "parse": "bing",
    },
}


# ═══════════════════════════════════════════
# HTML 解析器
# ═══════════════════════════════════════════
def _parse_sogou(html: str) -> List[dict]:
    results = []
    titles = re.findall(
        r'<h3[^>]*class="(?:vr-title[^"]*)"[^>]*>.*?<a[^>]*>(.*?)</a>',
        html, re.DOTALL
    )
    descriptions = re.findall(
        r'<div[^>]*class="(?:fz-mid[^"]*)"[^>]*>(.*?)</div>',
        html, re.DOTALL
    )
    links = re.findall(
        r'<h3[^>]*class="(?:vr-title[^"]*)"[^>]*>.*?<a[^>]*href="([^"]*)"',
        html, re.DOTALL
    )
    for i in range(min(len(titles), 10)):
        title = re.sub(r"<.*?>", "", titles[i]).strip()
        title = html_module.unescape(title)
        if not title or len(title) <= 3:
            continue
        snippet = ""
        if i < len(descriptions):
            snippet = re.sub(r"<.*?>", "", descriptions[i]).strip()
            snippet = html_module.unescape(snippet)[:200]
        url = links[i] if i < len(links) else ""
        if url.startswith("/link?url="):
            url = "https://www.sogou.com" + url
        elif url.startswith("/"):
            url = "https://www.sogou.com" + url
        results.append({"title": title, "snippet": snippet, "url": url})
        if len(results) >= 10:
            break
    return results


def _parse_google(html: str) -> List[dict]:
    results = []
    blocks = re.findall(
        r'<div[^>]*class="[^"]*g[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>.*?</div>',
        html, re.DOTALL
    )
    for block in blocks[:10]:
        title_match = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.DOTALL)
        if not title_match:
            continue
        title = re.sub(r"<.*?>", "", title_match.group(1)).strip()
        title = html_module.unescape(title)
        if not title or len(title) <= 3:
            continue
        snippet = ""
        desc_match = re.search(r'<[^>]*class="[^"]*[^"]*"[^>]*>(.*?)</[^>]*>', block, re.DOTALL)
        if desc_match:
            snippet = re.sub(r"<.*?>", "", desc_match.group(1)).strip()
            snippet = html_module.unescape(snippet)[:200]
        link_match = re.search(r'href="(/url\?q=([^"&]+))', block)
        url = ""
        if link_match:
            url = urllib.parse.unquote(link_match.group(2))
        if url:
            results.append({"title": title, "snippet": snippet, "url": url})
        if len(results) >= 10:
            break
    return results


def _parse_bing(html: str) -> List[dict]:
    results = []
    b_blocks = re.findall(
        r'<li[^>]*class="b_algo"[^>]*>.*?</li>',
        html, re.DOTALL
    )
    for block in b_blocks[:10]:
        title_match = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.DOTALL)
        if not title_match:
            continue
        title = re.sub(r"<.*?>", "", title_match.group(1)).strip()
        title = html_module.unescape(title)
        if not title or len(title) <= 3:
            continue
        desc_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
        snippet = ""
        if desc_match:
            snippet = re.sub(r"<.*?>", "", desc_match.group(1)).strip()
            snippet = html_module.unescape(snippet)[:200]
        link_match = re.search(r'<a[^>]*href="([^"]+)"', block)
        url = link_match.group(1) if link_match else ""
        results.append({"title": title, "snippet": snippet, "url": url})
        if len(results) >= 10:
            break
    return results


PARSERS = {
    "sogou": _parse_sogou,
    "google": _parse_google,
    "bing": _parse_bing,
}


# ═══════════════════════════════════════════
# 格式化输出（Web Search Skill 风格）
# ═══════════════════════════════════════════
def _format_results(query: str, results: List[dict], engine_name: str) -> str:
    """用结构化格式输出搜索结果"""
    if not results:
        return f'🔍 关于「{query}」未找到{engine_name}搜索结果，请换个关键词试试。'

    top_results = results[:5]
    core = top_results[0]
    lines = [
        f'🔍 **关于「{query}」的检索结果（{engine_name}）**',
        '',
        '### 📌 核心发现',
        f'**{core["title"]}**',
        f'> {core["snippet"]}',
        f'> 🔗 {core["url"]}',
        '',
        '### 📋 详细信息',
    ]

    for i, r in enumerate(top_results, 1):
        lines.append(
            f'{i}. **{r["title"]}**\n'
            f'   {"- " + r["snippet"] if r["snippet"] else ""}\n'
            f'   {"来源：" + r["url"] if r["url"] else ""}'
        )

    # 建议
    lines.append('')
    lines.append('### 💡 建议')
    lines.append(f'以上结果来自{engine_name}，如需更精确信息，可以尝试更具体的关键词搜索。')

    return '\n'.join(lines)


# ═══════════════════════════════════════════
# 搜索逻辑
# ═══════════════════════════════════════════
class SearchEngine:
    def __init__(self):
        self.engine: str = "sogou"
        self.max_results: int = 5

    def search(self, query: str, max_results: int = None) -> str:
        """执行搜索并返回格式化文本"""
        max_r = max_results or self.max_results
        engine_cfg = SEARCH_ENGINES[self.engine]
        engine_name = engine_cfg["name"]
        try:
            query_encoded = urllib.parse.quote(query)
            url = engine_cfg["url_pattern"].format(query=query_encoded, num=max_r)
            headers = dict(engine_cfg["headers"])
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode("utf-8", errors="replace")
                parser = PARSERS.get(engine_cfg["parse"])
                results = parser(html) if parser else []
            return _format_results(query, results, engine_name)
        except urllib.error.HTTPError as e:
            return f'🔍 搜索 HTTP 错误 ({e.code})：{e.reason}\n请稍后重试或更换搜索引擎。'
        except urllib.error.URLError as e:
            return f'🔍 搜索网络错误：{e.reason}\n请检查网络连接后重试。'
        except TimeoutError:
            return '🔍 搜索超时，请稍后重试。'
        except Exception as e:
            return f'🔍 搜索出错：{type(e).__name__} - {e}'


# ═══════════════════════════════════════════
# AstrBot 插件注册
# ═══════════════════════════════════════════
@register("astrbot_plugin_web_search", "openclaw", "多引擎搜索（搜狗/Google/Bing，含LLM函数调用）", "3.0.2")
class OpenClawSearchPlugin(Star):
    """多引擎搜索插件 — v3.0.2

    功能：
      - /websearch 命令：手动执行搜索
      - web_search 函数工具：AI 在对话中主动调用搜索

    配置项（data/plugin_config/openclaw_web_search.json）：
      engine:      搜索引擎，可选 sogou / google / bing（默认 sogou）
      max_results: 最大结果数（默认 5）
    """

    def __init__(self, context: Context):
        super().__init__(context)

        # 默认配置
        self._engine: str = "sogou"
        self._max_results: int = 5

        # 尝试加载配置文件
        try:
            cfg = context.get_config()
            self._engine = cfg.get("engine", "sogou")
            self._max_results = int(cfg.get("max_results", 5))
        except Exception:
            logger.info("[OpenClawSearch] 未找到配置文件，使用默认配置")

        # 校验引擎
        if self._engine not in SEARCH_ENGINES:
            logger.warning(
                f"[OpenClawSearch] 引擎 '{self._engine}' 无效，回退到 sogou。"
                f"可用引擎: {', '.join(SEARCH_ENGINES.keys())}"
            )
            self._engine = "sogou"

        # 初始化搜索引擎
        self.search_engine = SearchEngine()
        self.search_engine.engine = self._engine
        self.search_engine.max_results = self._max_results

        logger.info(f"[OpenClawSearch] v3.0.2 已就绪 | 引擎={self._engine} | 最大结果={self._max_results}")

    @filter.command("websearch")
    async def on_command(self, event: AstrMessageEvent, args: str):
        """使用方式：/websearch 搜索内容"""
        if not args or not args.strip():
            yield event.make_result().message(
                "🔍 请提供搜索内容，例如：/websearch 今日天气"
            )
            return
        query = args.strip()
        logger.info(f"[OpenClawSearch] 手动搜索: {query}")
        result = self.search_engine.search(query)
        yield event.make_result().message(result)
