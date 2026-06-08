# 🔍 多引擎搜索插件

AstrBot 多引擎联网搜索插件，支持**手动命令**和 **LLM 自动调用**，搜索结果原样返回不加工。

## ✨ 功能

- 🔎 `/websearch 关键词` — 手动搜索
- 🤖 `web_search` — LLM 可在对话中主动调用搜索
- 🌐 多引擎支持：**Bing**（默认）/ **搜狗** / **Google**
- 📊 结构化输出，结果直接呈现，无中间层筛选
- ⚙️ 支持插件配置界面，一键切换搜索引擎

## 📦 安装

将整个 `astrbot_plugin_web_search` 目录放入 AstrBot 的 `data/plugin/` 目录后重启：

```
data/plugin/astrbot_plugin_web_search/
├── metadata.yaml
├── main.py
├── _conf_schema.json
├── CHANGELOG.md
└── README.md
```

## ⚙️ 配置

在 AstrBot 管理面板 → 插件管理 → 多引擎搜索 → 配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `engine` | 搜索引擎 (bing / sogou / google) | bing |
| `max_results` | 最大结果数 (1-10) | 8 |

## 📝 使用示例

```
/websearch 今日天气

🔍 **「今日天气」— Bing搜索结果（8 条）**

1. **全国大部地区气温回升 南方多阴雨**
   中央气象台预计...
   🔗 https://...

2. **北京今日晴转多云**
   气温18℃~28℃，风力3-4级
   🔗 https://...
```

## 🙋 FAQ

**Q: 函数工具看不到？**  
A: 需要在 AstrBot 管理面板 → 函数工具 → 找到 `web_search` → 点击启用。

**Q: 搜索不到结果？**  
A: 尝试在配置中切换到其他搜索引擎（推荐 Bing，国内可直连）。

**Q: 搜索结果感觉被 AI 加工过？**  
A: v3.1.3 起已移除中间层，LLM 拿到的是原始搜索结果，不再强制要求 AI 总结。

## 📄 License

MIT
