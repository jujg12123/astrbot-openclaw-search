"""OpenClaw Web Search Plugin for AstrBot

功能：
  1. /websearch 命令 — 手动执行联网搜索
  2. web_search LLM函数工具 — 让AI在对话中**主动调用**搜索

用法：
  把本文件复制到 AstrBot 的 data/plugin/ 目录
  插件名会自动注册为 openclaw_web_search
"""

import json
import re
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional

# 从 astrbot API 导入（AstrBot 运行时自动提供）
from astrbot.api import star
from astrbot.api.all import llm_tool
from astrbot.api.event import AstrMessageEvent


@star.register(name="openclaw_web_search", author="openclaw",
                desc="OpenClaw内置web_search工具封装（含LLM函数调用）",
                version="1.0.0")
class OpenClawSearchPlugin(star.Star):
    """OpenClaw内置web_search功能封装插件

    功能：
      - /websearch 命令：手动执行联网搜索
      - web_search 函数工具：让AI在对话中主动调用搜索

    配置项（data/plugin_config/openclaw_web_search.json 或插件配置）：
      enabled: 是否启用
      max_results: 最大搜索结果数（默认5）
      search_lang: 搜索语言，zh或en（默认zh）
      freshness: 时间过滤，可选 day/week/month/year
    """

    def __init__(self, context, config=None):
        super().__init__(context)
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.max_results = self.config.get("max_results", 5)
        self.search_lang = self.config.get("search_lang", "zh")
        self.freshness = self.config.get("freshness", "")

    # ──────────────────────────────────────────────
    # 1. 命令：/websearch
    # ──────────────────────────────────────────────
    @star.register(name="websearch", desc="使用OpenClaw内置搜索工具联网搜索")
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

    # ──────────────────────────────────────────────
    # 2. LLM 函数工具：web_search
    #    AI在对话中会自动感知此工具并可能主动调用
    # ──────────────────────────────────────────────
    @llm_tool(name="web_search", desc="Search the web for real-time information. Use when you need current facts, news, or data you don't have. Returns structured results with titles, snippets, and URLs.")
    async def web_search_tool(
        self,
        event: AstrMessageEvent,
        query: str,
        max_results: Optional[int] = 5,
        language: Optional[str] = "zh",
        freshness: Optional[str] = "",
    ) -> str:
        """Search the web for real-time information.

        Args:
            query (string): The search query (required).
            max_results (number): Number of results to return (default: 5).
            language (string): Search language, 'zh' or 'en' (default: 'zh').
            freshness (string): Time filter — 'day', 'week', 'month', 'year', or '' for all time.
        """
        result = await self._do_search(
            query,
            max_results=max_results or self.max_results,
            lang=language or self.search_lang,
            freshness=freshness or self.freshness,
        )
        return result

    # ──────────────────────────────────────────────
    # 核心搜索逻辑
    # ──────────────────────────────────────────────
    async def _do_search(
        self,
        query: str,
        max_results: int = None,
        lang: str = None,
        freshness: str = None,
    ) -> str:
        """执行搜索并返回格式化文本"""
        max_r = max_results or self.max_results
        search_lang = lang or self.search_lang
        fresh = freshness or self.freshness

        try:
            query_encoded = urllib.parse.quote(query)
            search_url = f"https://www.google.com/search?q={query_encoded}&num={max_r}&hl={search_lang[:2]}"

            if fresh:
                search_url += f"&tbs=qdr:{fresh}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8" if search_lang.startswith("zh") else "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            req = urllib.request.Request(search_url, headers=headers)

            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode("utf-8")
                results = self._parse_search_results(html, query)

            if not results:
                return f"No results found for \"{query}\"."

            lines = [f"Search results for \"{query}\":\n"]
            for i, r in enumerate(results, 1):
                lines.append(
                    f"[{i}] {r['title']}\n"
                    f"    {r['snippet']}\n"
                    f"    URL: {r['url']}"
                )
            return "\n\n".join(lines)

        except urllib.error.HTTPError as e:
            return f"Search HTTP error: {e.code} {e.reason}"
        except urllib.error.URLError as e:
            return f"Search network error: {e.reason}"
        except TimeoutError:
            return "Search timed out. Please try again."
        except Exception as e:
            return f"Search error: {type(e).__name__}: {e}"

    # ──────────────────────────────────────────────
    # 解析 & 格式化
    # ──────────────────────────────────────────────
    @staticmethod
    def _parse_search_results(html: str, query: str) -> list:
        results = []
        title_pattern = r'<h3[^>]*>(.*?)</h3>'
        link_pattern = r'<a[^>]*href="([^"]*?)"[^>]*>'

        titles = re.findall(title_pattern, html, re.IGNORECASE | re.DOTALL)
        links = re.findall(link_pattern, html, re.IGNORECASE)

        for i in range(min(len(titles), 5)):
            title = re.sub(r"<.*?>", "", titles[i]).strip()
            if title and len(title) > 3:
                url = links[i] if i < len(links) else ""
                if url.startswith("/"):
                    url = "https://www.google.com" + url
                elif url and not url.startswith("http"):
                    url = "https://" + url
                if not url:
                    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": "",
                })
            if len(results) >= 5:
                break

        return results
