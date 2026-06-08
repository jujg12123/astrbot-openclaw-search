# 🔍 多引擎搜索插件

AstrBot 多引擎联网搜索插件，支持**手动命令**和 **LLM 自动调用**。

## ✨ 功能

- 🔎 `/websearch 关键词` — 手动搜索
- 🤖 `web_search` — LLM 可在对话中主动调用搜索
- 🌐 多引擎支持：**搜狗**（推荐） / **Google** / **Bing**
- 📊 结构化输出：核心发现 → 详细信息 → 实用建议
- ⚙️ 支持插件配置界面，一键切换搜索引擎

## 📦 安装

将整个 `astrbot_plugin_web_search` 目录放入 AstrBot 的 `data/plugin/` 目录后重启：

```
data/plugin/astrbot_plugin_web_search/
├── metadata.yaml
├── main.py
└── _conf_schema.json
```

## ⚙️ 配置

在 AstrBot 管理面板 → 插件管理 → 多引擎搜索 → 配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `engine` | 搜索引擎 (sogou / google / bing) | sogou |
| `max_results` | 最大结果数 (1-10) | 5 |

## 📝 使用示例

```
/websearch 今日天气

🔍 **关于「今日天气」的搜索结果（搜狗）**

📌 **核心发现**
**全国大部地区气温回升 南方多阴雨**
> 中央气象台预计...
> 🔗 https://...

📋 **详细信息**
1. **北京今日晴转多云**
   - 气温18℃~28℃，风力3-4级
   🔗 https://...

💡 以上结果来自搜狗，如需更精确信息可尝试更具体的关键词。
```

## 🙋 FAQ

**Q: 函数工具看不到？**  
A: 需要在 AstrBot 管理面板 → 函数工具 → 找到 `web_search` → 点击启用。

**Q: 搜索不到结果？**  
A: 尝试在配置中切换到其他搜索引擎（推荐搜狗）。

## 📄 License

MIT
