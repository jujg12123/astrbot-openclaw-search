"""多引擎搜索插件 for AstrBot

功能：
  1. /websearch [关键词] — 手动触发搜索
  2. web_search — LLM函数工具，AI在对话中可**主动调用**搜索

支持的搜索引擎（通过配置文件选择）：
  - sogou    搜狗搜索（中文友好，推荐）
  - google   Google 搜索
  - bing     Bing 搜索

用法：
  把本目录复制到 AstrBot 的 data/plugin/ 目录
  插件名会自动注册为 openclaw_web_search
"""

import json
import re
import urllib.request
import urllib.error
import urllib.parse
import html as html_module
from typing import Optional

# ──────────────────────────────────────────────
# 搜索引擎定义
# ──────────────────────────────────────────────
SEARCH_ENGINES = {
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


# ──────────────────────────────────────────────
# 各引擎解析器
# ──────────────────────────────────────────────
def _parse_sogou(html: str) -> list:
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
            snippet = html_module.unescape(snippet)[:150]
        url = links[i] if i < len(links) else ""
        if url.startswith("/link?url="):
            url = "https://www.sogou.com" + url
        elif url.startswith("/"):
            url = "https://www.sogou.com" + url
        elif not url:
            url = ""
        results.append({"title": title, "snippet": snippet, "url": url})
        if len(results) >= 10:
            break
    return results


def _parse_google(html: str) -> list:
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
            snippet = html_module.unescape(snippet)[:150]
        link_match = re.search(r'href="(/url\?q=([^"&]+))', block)
        url = ""
        if link_match:
            url = urllib.parse.unquote(link_match.group(2))
        if url:
            results.append({"title": title, "snippet": snippet, "url": url})
        if len(results) >= 10:
            break
    return results


def _parse_bing(html: str) -> list:
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
            snippet = html_module.unescape(snippet)[:150]
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


# ──────────────────────────────────────────────
# AstrBot 插件注册
# ──────────────────────────────────────────────
from astrbot.api import star
from astrbot.api.all import llm_tool
from astrbot.api.event import AstrMessageEvent


@star.register(name="openclaw_web_search", author="openclaw",
                desc="多引擎搜索（搜狗/Google/Bing，含LLM函数调用）",
                version="3.0.0")
class OpenClawSearchPlugin(star.Star):
    """多引擎搜索插件

    功能：
      - /websearch 命令：手动执行搜索
      - web_search 函数工具：AI在对话中主动调用搜索

    配置项（data/plugin_config/openclaw_web_search.json）：
      engine:     搜索引擎，可选 sogou / google / bing（默认 sogou）
      enabled:    是否启用（默认 true）
      max_results: 最大结果数（默认 5）
    """

    def __init__(self, context, config=None):
        super().__init__(context)
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.engine = self.config.get("engine", "sogou")
        self.max_results = self.config.get("max_results", 5)
        if self.engine not in SEARCH_ENGINES:
            self.logger.warn(
                f"[OpenClawSearch] 引擎 '{self.engine}' 无效，"
                f"默认使用 sogou。可用引擎: {', '.join(SEARCH_ENGINES.keys())}"
            )
            self.engine = "sogou"

    @star.register(name="websearch", desc="使用搜狗/Google/Bing搜索联网信息")
    async def on_command(self, event: AstrMessageEvent, args: str):
        """使用方式：/websearch 搜索内容"""
        if not args or not args.strip():
            yield event.make_result().message(
                "请提供搜索内容，例如：/websearch 今日天气"
            )
            return
        query = args.strip()
        result = await self._do_search(query)
        yield event.make_result().message(result)

    @llm_tool(name="web_search", desc="搜索互联网获取实时信息。当你需要了解最新事实、新闻或你没有的数据时使用。返回包含标题、摘要和链接的结构化结果。")
    async def web_search_tool(
        self,
        event: AstrMessageEvent,
        query: str,
        max_results: Optional[int] = 5,
    ) -> str:
        """搜索互联网获取实时信息。

        Args:
            query (string): 搜索关键词（必填）。
            max_results (number): 返回结果数量（默认5）。
        """
        result = await self._do_search(
            query,
            max_results=max_results or self.max_results,
        )
        return result

    async def _do_search(self, query: str, max_results: int = None) -> str:
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
            if not results:
                return f'未找到 "{query}" 的{engine_name}搜索结果。'
            lines = [f'"{query}" 的{engine_name}搜索（共找到 {len(results)} 条结果）：\n']
            for i, r in enumerate(results, 1):
                lines.append(
                    f"[{i}] {r['title']}\n"
                    f"    {r['snippet']}\n"
                    f"    URL: {r['url']}"
                )
            return "\n\n".join(lines)
        except urllib.error.HTTPError as e:
            return f"搜索 HTTP 错误: {e.code} {e.reason}"
        except urllib.error.URLError as e:
            return f"搜索网络错误: {e.reason}"
        except TimeoutError:
            return "搜索超时，请稍后重试。"
        except Exception as e:
            return f"搜索出错: {type(e).__name__}: {e}"
