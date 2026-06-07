# 百度搜索插件 for AstrBot

## 功能
- **/websearch [关键词]** — 手动触发百度搜索
- **web_search** — LLM函数工具，AI在对话中可**主动调用**搜索

## 安装

1. 复制插件文件到 AstrBot 插件目录：
   ```bash
   cp astrbot_plugin_openclaw_search.py <AstrBot数据目录>/data/plugin/
   ```

2. 重启 AstrBot

## 配置（可选）

创建配置文件 `<AstrBot数据目录>/data/plugin_config/openclaw_web_search.json`：

```json
{
  "enabled": true,
  "max_results": 5
}
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| enabled | true | 是否启用 |
| max_results | 5 | 最大结果数 |

## 说明

由于百度搜索有严格反爬机制，插件使用搜狗搜索作为后端获取结果，前端统一显示为"百度搜索"。

## 依赖

- Python 3.8+
- 网络连通性
- 无需额外 pip 包
