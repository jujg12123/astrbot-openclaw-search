# 多引擎搜索插件 for AstrBot

## 功能
- **/websearch [关键词]** — 手动触发搜索
- **web_search** — LLM函数工具，AI在对话中可**主动调用**搜索

## 支持的搜索引擎
| 引擎 | 说明 | 推荐场景 |
|------|------|----------|
| `sogou` | 搜狗搜索 | 中文搜索，稳定可靠 |
| `google` | Google 搜索 | 英文/综合搜索 |
| `bing` | Bing 搜索 | 备用搜索引擎 |

## 安装

1. 复制插件文件到 AstrBot 插件目录：
   ```bash
   cp astrbot_plugin_openclaw_search.py <AstrBot数据目录>/data/plugin/
   ```

2. 创建配置文件（在 `<AstrBot数据目录>/data/plugin_config/` 目录下）：

   文件名：**`openclaw_web_search.json`**

   内容：
   ```json
   {
     "engine": "sogou",
     "enabled": true,
     "max_results": 5
   }
   ```

   | 参数 | 默认值 | 说明 |
   |------|--------|------|
   | engine | `sogou` | 搜索引擎，可选 `sogou` / `google` / `bing` |
   | enabled | `true` | 是否启用 |
   | max_results | `5` | 最大结果数 |

3. 重启 AstrBot

## 使用

### 手动搜索
```
/websearch Python 编程教程
```

### AI 自动调用
在对话中，当你提出需要最新信息的问题时，AI 会自动调用 web_search 函数工具。

## 切换搜索引擎

只需修改配置文件中的 `engine` 值：

- 搜狗：`"engine": "sogou"`（默认）
- Google：`"engine": "google"`
- Bing：`"engine": "bing"`

修改后重启 AstrBot 生效。

## 依赖

- Python 3.8+
- 网络连通性
- 无需额外 pip 包
