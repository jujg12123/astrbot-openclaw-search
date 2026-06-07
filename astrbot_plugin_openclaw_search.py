"""百度搜索插件 for AstrBot

功能：
  1. /websearch 命令 — 手动执行联网搜索（百度）
  2. web_search LLM函数工具 — 让AI在对话中**主动调用**搜索（百度）

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
                desc="百度搜索插件（含LLM函数调用）",
                version="2.0.0")
class OpenClawSearchPlugin(star.Star):
    """百度搜索插件

    功能：
      - /websearch 命令：手动执行百度联网搜索
      - web_search 函数工具：让AI在对话中主动调用搜索

    配置项（data/plugin_config/openclaw_web_search.json 或插件配置）：
      enabled: 是否启用
      max_results: 最大搜索结果数（默认5）
    """

    def __init__(self, context, config=None):
        super().__init__(context)
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.max_results = self.config.get("max_results", 5)

    # ──────────────────────────────────────────────
    # 1. 命令：/websearch
    # ──────────────────────────────────────────────
    @star.register(name="websearch", desc="使用百度搜索联网搜索")
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
    @llm_tool(name="web_search", desc="搜索互联网获取实时信息。当你需要了解最新事实、新闻或你没有的数据时使用。返回包含标题、摘要和链接的结构化结果。")
    async def web_search_tool(
        self,
        event: AstrMessageEvent,
        query: str,
        max_results: Optional[int] = 5,
    ) -> str:
        """百度搜索互联网获取实时信息。

        Args:
            query (string): 搜索关键词（必填）。
            max_results (number): 返回结果数量（默认5）。
        """
        result = await self._do_search(
            query,
            max_results=max_results or self.max_results,
        )
        return result

    # ──────────────────────────────────────────────
    # 核心搜索逻辑（百度/搜狗）
    # ──────────────────────────────────────────────
    async def _do_search(self, query: str, max_results: int = None) -> str:
        """执行百度/搜狗搜索并返回格式化文本"""
        max_r = max_results or self.max_results

        try:
            query_encoded = urllib.parse.quote(query)
            search_url = f"https://www.sogou.com/web?query={query_encoded}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }

            req = urllib.request.Request(search_url, headers=headers)

            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode("utf-8", errors="replace")
                results = self._parse_search_results(html, query)

            if not results:
                return f'未找到 "{query}" 的搜索结果。'

            lines = [f'"{query}" 的百度搜索（共找到 {len(results)} 条结果）：\n']
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

    # ──────────────────────────────────────────────
    # 解析搜狗搜索结果并格式化
    # ──────────────────────────────────────────────
    @staticmethod
    def _parse_search_results(html: str, query: str) -> list:
        import html as html_module
        results = []

        # 提取标题块: h3.vr-title 下的 a 标签
        titles = re.findall(
            r'<h3[^>]*class="(?:vr-title[^"]*)"[^>]*>.*?<a[^>]*>(.*?)</a>',
            html, re.DOTALL
        )

        # 提取摘要: div.fz-mid
        descriptions = re.findall(
            r'<div[^>]*class="(?:fz-mid[^"]*)"[^>]*>(.*?)</div>',
            html, re.DOTALL
        )

        # 提取链接
        links = re.findall(
            r'<h3[^>]*class="(?:vr-title[^"]*)"[^>]*>.*?<a[^>]*href="([^"]*)"',
            html, re.DOTALL
        )

        for i in range(min(len(titles), 5)):
            title = re.sub(r"<.*?>", "", titles[i]).strip()
            title = html_module.unescape(title)

            if not title or len(title) <= 3:
                continue

            # 提取摘要
            snippet = ""
            if i < len(descriptions):
                snippet = re.sub(r"<.*?>", "", descriptions[i]).strip()
                snippet = html_module.unescape(snippet)[:150]

            # 处理链接
            url = links[i] if i < len(links) else ""
            if url.startswith("/link?url="):
                # 搜狗中间件链接，保留完整路径
                url = "https://www.sogou.com" + url
            elif url.startswith("/"):
                url = "https://www.sogou.com" + url
            elif not url:
                url = f"https://www.sogou.com/web?query={urllib.parse.quote(query)}"

            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
            })

            if len(results) >= 5:
                break

        return results
