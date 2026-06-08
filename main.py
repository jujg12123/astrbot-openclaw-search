"""多引擎搜索插件 for AstrBot

功能：
  1. /websearch [关键词] — 手动触发搜索
  2. web_search — LLM 函数工具，AI 在对话中可**主动调用**搜索

支持的搜索引擎：
  - sogou    搜狗搜索（中文友好，推荐）
  - google   Google 搜索
  - bing     Bing 搜索
"""

import asyncio
import re
import urllib.request
import urllib.error
import urllib.parse
import html as html_module

from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

# ═══════════════════════ 搜索引擎定义 ═══════════════════════
SEARCH_ENGINES = {
    "sogou": {
        "name": "搜狗",
        "url": "https://www.sogou.com/web?query={query}",
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; AstrBot/1.0)",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    },
    "google": {
        "name": "Google",
        "url": "https://www.google.com/search?q={query}&num={num}&hl=zh-CN",
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; AstrBot/1.0)",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    },
    "bing": {
        "name": "Bing",
        "url": "https://www.bing.com/search?q={query}&count={num}",
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; AstrBot/1.0)",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    },
}


# ═══════════════════════ HTML 解析器 ═══════════════════════
def _parse_sogou(html: str) -> list:
    results = []
    titles = re.findall(r'<h3[^>]*class="(?:vr-title[^"]*)"[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)
    descs = re.findall(r'<div[^>]*class="(?:fz-mid[^"]*)"[^>]*>(.*?)</div>', html, re.DOTALL)
    links = re.findall(r'<h3[^>]*class="(?:vr-title[^"]*)"[^>]*>.*?<a[^>]*href="([^"]*)"', html, re.DOTALL)
    for i in range(min(len(titles), 10)):
        title = html_module.unescape(re.sub(r"<.*?>", "", titles[i]).strip())
        if not title or len(title) <= 3:
            continue
        snippet = html_module.unescape(re.sub(r"<.*?>", "", descs[i]).strip())[:200] if i < len(descs) else ""
        url = links[i] if i < len(links) else ""
        if url.startswith("/"):
            url = "https://www.sogou.com" + url
        results.append({"title": title, "snippet": snippet, "url": url})
        if len(results) >= 10:
            break
    return results


def _parse_google(html: str) -> list:
    results = []
    blocks = re.findall(r'<div[^>]*class="[^"]*g[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>.*?</div>', html, re.DOTALL)
    for block in blocks[:10]:
        tm = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.DOTALL)
        if not tm: continue
        title = html_module.unescape(re.sub(r"<.*?>", "", tm.group(1)).strip())
        if not title or len(title) <= 3: continue
        sm = re.search(r'<[^>]*class="[^"]*[^"]*"[^>]*>(.*?)</[^>]*>', block, re.DOTALL)
        snippet = html_module.unescape(re.sub(r"<.*?>", "", sm.group(1)).strip())[:200] if sm else ""
        lm = re.search(r'href="(/url\?q=([^"&]+))', block)
        url = urllib.parse.unquote(lm.group(2)) if lm else ""
        if url:
            results.append({"title": title, "snippet": snippet, "url": url})
        if len(results) >= 10: break
    return results


def _parse_bing(html: str) -> list:
    results = []
    blocks = re.findall(r'<li[^>]*class="b_algo"[^>]*>.*?</li>', html, re.DOTALL)
    for block in blocks[:10]:
        tm = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.DOTALL)
        if not tm: continue
        title = html_module.unescape(re.sub(r"<.*?>", "", tm.group(1)).strip())
        if not title or len(title) <= 3: continue
        sm = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
        snippet = html_module.unescape(re.sub(r"<.*?>", "", sm.group(1)).strip())[:200] if sm else ""
        lm = re.search(r'<a[^>]*href="([^"]+)"', block)
        url = lm.group(1) if lm else ""
        results.append({"title": title, "snippet": snippet, "url": url})
        if len(results) >= 10: break
    return results


PARSERS = {"sogou": _parse_sogou, "google": _parse_google, "bing": _parse_bing}


# ═══════════════════════ 格式化输出 ═══════════════════════
def _format_results(query: str, results: list, engine_name: str) -> str:
    if not results:
        return f'🔍 「{query}」未找到相关结果，请换个关键词试试。'
    top = results[:5]
    core = top[0]
    lines = [
        f'🔍 **关于「{query}」的搜索结果（{engine_name}）**',
        '',
        '📌 **核心发现**',
        f'**{core["title"]}**',
        f'> {core["snippet"]}',
        f'> 🔗 {core["url"]}',
        '',
        '📋 **详细信息**',
    ]
    for i, r in enumerate(top, 1):
        lines.append(f'{i}. **{r["title"]}**')
        if r["snippet"]:
            lines.append(f'   - {r["snippet"]}')
        if r["url"]:
            lines.append(f'   🔗 {r["url"]}')
    lines.append('')
    lines.append(f'💡 以上结果来自{engine_name}，如需更精确信息可尝试更具体的关键词。')
    return '\n'.join(lines)


# ═══════════════════════ 搜索引擎 ═══════════════════════
class SearchEngine:
    def __init__(self):
        self.engine: str = "sogou"
        self.max_results: int = 5

    def search_sync(self, query: str, max_results: int = None) -> str:
        """同步搜索（供 LLM 函数工具调用）"""
        max_r = max_results or self.max_results
        cfg = SEARCH_ENGINES.get(self.engine, SEARCH_ENGINES["sogou"])
        engine_name = cfg["name"]
        try:
            url = cfg["url"].format(query=urllib.parse.quote(query), num=max_r)
            req = urllib.request.Request(url, headers=dict(cfg["headers"]))
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            results = PARSERS.get(self.engine, _parse_sogou)(html)
            return _format_results(query, results, engine_name)
        except urllib.error.HTTPError as e:
            return f'🔍 搜索 HTTP 错误({e.code})，请稍后重试。'
        except urllib.error.URLError as e:
            return f'🔍 搜索网络错误：{e.reason}'
        except TimeoutError:
            return '🔍 搜索超时，请稍后重试。'
        except Exception as e:
            return f'🔍 搜索出错：{type(e).__name__} - {e}'


# ═══════════════════════ LLM 函数工具 ═══════════════════════
@dataclass
class WebSearchTool(FunctionTool[AstrAgentContext]):
    """llm 可调用的搜索工具"""
    name: str = "web_search"
    description: str = (
        "搜索互联网获取最新信息。当需要了解实时资讯、新闻事实、天气、百科等"
        "对话外的信息时调用。返回结构化结果，包含核心发现和详细条目。"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "用户想要搜索的关键词，请提取核心提问内容。"
                },
                "max_results": {
                    "type": "integer",
                    "description": "期望返回的结果数量，默认5。",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    )

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)
        logger.info(f"[WebSearch] LLM 调用搜索: '{query}'")
        # 用 asyncio.to_thread 避免阻塞
        result = await asyncio.to_thread(self._engine.search_sync, query, max_results)
        return ToolExecResult(result)


# ═══════════════════════ 插件注册 ═══════════════════════
@register("astrbot_plugin_web_search", "openclaw", "多引擎搜索（搜狗/Google/Bing）", "3.0.3")
class WebSearchPlugin(Star):
    """多引擎搜索插件

    功能：
      - /websearch 命令：手动执行搜索，结构化输出
      - web_search 函数工具：AI 在对话中主动调用搜索

    配置（data/plugin_config/astrbot_plugin_web_search.json）：
      engine:      搜索引擎（sogou / google / bing）
      max_results: 最大结果数（默认5）
    """

    def __init__(self, context: Context):
        super().__init__(context)

        # 读取配置
        self._engine = "sogou"
        self._max_results = 5
        try:
            cfg = context.get_config()
            self._engine = cfg.get("engine", "sogou")
            self._max_results = int(cfg.get("max_results", 5))
        except Exception:
            pass

        if self._engine not in SEARCH_ENGINES:
            self._engine = "sogou"

        # 初始化搜索后端
        self._search = SearchEngine()
        self._search.engine = self._engine
        self._search.max_results = self._max_results

        # 注册 LLM 函数工具
        tool = WebSearchTool()
        tool._engine = self._search   # 绑定后端
        self.web_search_tool = tool

        logger.info(f"[WebSearch] v3.0.3 就绪 | 引擎={self._engine} | 最大结果={self._max_results}")

    @filter.command("websearch")
    async def on_command(self, event: AstrMessageEvent, args: str):
        """手动搜索: /websearch 关键词"""
        if not args or not args.strip():
            yield event.make_result().message("🔍 用法：/websearch 关键词")
            return
        result = await asyncio.to_thread(self._search.search_sync, args.strip())
        yield event.make_result().message(result)
