# Tarot Search Tool

一个基于 Rider–Waite–Smith（伟特）塔罗牌的中文检索与抽牌工具。项目使用 Flask 提供页面与 API，牌义数据和牌面图片均保存在本地。

Vibe coded with [Claude Sonnet 4.6](https://www.anthropic.com/claude) (`claude-sonnet-4-6`).

## 功能

- **78 张牌完整收录**：包含 22 张大阿卡那与 56 张小阿卡那
- **多字段检索**：支持中文牌名、英文牌名、编号、花色、关键词及释义内容
- **牌组筛选**：可按大阿卡那、圣杯、权杖、宝剑和星币浏览
- **正逆位释义**：展示正位与逆位关键词、详细解释和来源链接
- **牌面插图**：使用 Rider–Waite–Smith 版本图片
- **随机抽牌**：支持一次抽取 1–5 张牌，并随机决定正逆位
- **量子随机数**：优先使用澳大利亚国立大学的 ANU QRNG；请求失败时自动回退到 Python 伪随机数
- **抽牌结果保留**：同一浏览器标签页内刷新后仍可恢复上一次结果
- **访问统计**：使用本地 SQLite 数据库记录主要页面访问；过滤常见爬虫，并对同一访客在 30 分钟内的重复访问去重

## 页面与 API

| 路径 | 用途 |
| --- | --- |
| `/` | 塔罗牌检索与浏览 |
| `/draw` | 随机抽牌 |
| `/about` | 项目、数据来源及访问统计 |
| `/draw/about` | 抽牌和随机数生成方式说明 |
| `/api/all` | 返回全部牌数据 |
| `/api/search?q=关键词` | 搜索牌数据 |
| `/api/draw?n=1` | 抽取 1–5 张牌 |
| `/api/stats` | 返回页面访问统计 |

## 项目结构

```text
tarot_search_tool/
├── app.py                 # Flask 应用、API、抽牌与访问统计
├── scraper.py             # 牌义数据抓取脚本
├── download_images.py     # 牌面图片下载脚本
├── requirements.txt       # Python 依赖
├── data/
│   ├── tarot.json         # 78 张牌的牌义数据
│   └── stats.db           # 运行时生成的访问统计数据库（不纳入 Git）
├── static/
│   └── images/            # 78 张牌面图片
└── templates/
    ├── index.html         # 检索主页
    ├── draw.html          # 抽牌页面
    ├── about.html         # 项目说明页面
    ├── draw_about.html    # 抽牌方式说明页面
    └── sources.html       # 旧版数据来源页面（当前会由 /sources 跳转至 /about）
```

## 本地启动

需要 Python 3 和 pip。

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

启动后访问 <http://localhost:7777>。

## 生产环境运行

依赖中包含 Gunicorn，可以在兼容的平台上运行：

```bash
gunicorn app:app
```

生产环境不要直接使用 `python app.py` 中的 Flask debug 服务器。应用会在 `data/` 目录创建 `stats.db`，因此部署时需要确保该目录可写；如果需要保留访问统计，还应为它配置持久化存储。

## 更新数据与图片

从牌义来源重新抓取并生成 `data/tarot.json`：

```bash
python scraper.py
```

重新下载牌面图片：

```bash
python download_images.py
```

这些脚本会访问外部网站；运行前请确认网络可用，并在更新后检查数据结构与图片是否完整。

## 数据来源

- 牌义释义：[塔罗网 w.taluo.com](https://w.taluo.com)
- 牌面插图：[metabismuth/tarot-json](https://github.com/metabismuth/tarot-json)（Rider–Waite–Smith，CC0）
- 随机数服务：[ANU Quantum Random Numbers Server](https://qrng.anu.edu.au/)

牌义仅供学习、娱乐与自我反思，不应替代医疗、法律、财务或其他专业意见。
