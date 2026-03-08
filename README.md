# Tarot Search Tool

基于韦特塔罗牌的中文检索工具，支持按牌名搜索，展示正逆位释义、关键词与牌面图像。

## 功能

- **全牌检索** — 覆盖全部 78 张塔罗牌（22 张大阿卡那 + 56 张小阿卡那），支持中文牌名、英文名、花色模糊匹配
- **正逆位释义** — 每张牌展示完整的正位与逆位含义，附各自关键词标签
- **牌面描述** — 提取自塔罗网的牌面图像解读，帮助理解牌义象征
- **伟特塔罗插图** — 卡片展示 Rider-Waite-Smith 版本插图缩略图（公共领域，CC0）
- **详情弹窗** — 点击任意卡片可弹出大图详情，包含完整释义与原始参考链接
- **牌组筛选** — 顶部 filter 可按大阿卡那 / 圣杯 / 权杖 / 宝剑 / 星币快速分组浏览
- **数据来源页** — `/sources` 页面列出所有 78 张牌的原始参考链接（来自塔罗网）

## 数据来源

- 牌义释义：[塔罗网 w.taluo.com](https://w.taluo.com)
- 牌面插图：[metabismuth/tarot-json](https://github.com/metabismuth/tarot-json)（Rider-Waite-Smith，CC0）

## 启动

```bash
cd tarot_search_tool
d:/Documents/Projects/.venv/Scripts/python.exe app.py
```

打开浏览器访问 http://localhost:7777

## 更新牌义数据

牌义数据存储在 `data/tarot.json`，可通过爬虫脚本从塔罗网重新抓取：

```bash
python scraper.py
```

抓取完成后重启 Flask 即可生效。

## 项目结构

```
tarot_search_tool/
├── app.py              Flask 后端，提供搜索 API 与页面路由
├── scraper.py          数据抓取脚本
├── data/
│   └── tarot.json      78 张牌的完整数据
└── templates/
    ├── index.html      主检索页
    └── sources.html    数据来源页
```
