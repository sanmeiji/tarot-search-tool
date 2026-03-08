"""
从 w.taluo.com 抓取所有 78 张塔罗牌的详细释义，合并进 tarot.json。
运行：python scraper.py
"""
import json
import time
import os
import sys
import requests
from bs4 import BeautifulSoup

# Windows 终端 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://w.taluo.com"

# 大阿卡那 URL slug（正逆位加 z/n）
MAJOR_SLUGS = {
    1: "yr",    # 愚者
    2: "mfs",   # 魔法师
    3: "njs",   # 女祭司
    4: "nh",    # 女皇
    5: "hd",    # 皇帝
    6: "jh",    # 教皇
    7: "lr",    # 恋人
    8: "zc",    # 战车
    9: "ll",    # 力量
    10: "ys",   # 隐者
    11: "myzl", # 命运之轮
    12: "zy",   # 正义
    13: "ddr",  # 倒吊者
    14: "ss",   # 死神
    15: "jz",   # 节制
    16: "em",   # 恶魔
    17: "gt",   # 高塔
    18: "xx",   # 星星
    19: "yl",   # 月亮
    20: "ty",   # 太阳
    21: "sp",   # 审判
    22: "sj",   # 世界
}

# 小阿卡那 URL 前缀与数字映射
MINOR_PREFIX = {
    "圣杯": "sb",
    "权杖": "qz",
    "宝剑": "bj",
    "星币": "xb",
}

MINOR_NUM_MAP = {
    "A": "1",
    "2": "2", "3": "3", "4": "4", "5": "5",
    "6": "6", "7": "7", "8": "8", "9": "9", "10": "10",
    "侍从": "sc",
    "骑士": "qs",
    "皇后": "hh",
    "国王": "gw",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Referer": "https://w.taluo.com/",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def get_url(card):
    """根据卡牌信息生成正逆位 URL"""
    if card["arcana"] == "major":
        slug = MAJOR_SLUGS.get(card["id"])
        if not slug:
            return None, None
        return (
            f"{BASE}/da/{slug}z.php",
            f"{BASE}/da/{slug}n.php",
        )
    else:
        prefix = MINOR_PREFIX.get(card["suit"])
        num = MINOR_NUM_MAP.get(card["number"])
        if not prefix or not num:
            return None, None
        return (
            f"{BASE}/{prefix}/{prefix}{num}z.php",
            f"{BASE}/{prefix}/{prefix}{num}n.php",
        )


def fetch_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        r.encoding = "utf-8"
        return r.text
    except Exception as e:
        sys.stdout.buffer.write(f"  !! failed {url}: {e}\n".encode("utf-8"))
        return None


def parse_card_page(html):
    """解析单张牌页面，提取关键词和完整牌面细节"""
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    result = {}

    # 1. 关键词（在 header 里，先提取再移除）
    kw_tag = soup.find(string=lambda t: t and "关键词" in t and len(t) < 100)
    if kw_tag:
        kw = str(kw_tag).replace("关键词", "").lstrip("：:").strip()
        if kw:
            result["keywords"] = kw

    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]

    # 2. 牌面细节：收集从"牌面细节"/"牌义推演"到下一个段落标题之前的所有段落
    START_MARKERS = {"牌义推演", "牌面细节"}
    STOP_MARKERS  = {"核心提示", "知识扩展", "牌义延伸", "想得到专业", "Copyright", "版权"}

    desc_lines = []
    collecting = False
    for line in lines:
        if not collecting:
            if any(m in line for m in START_MARKERS):
                collecting = True
        else:
            if any(m in line for m in STOP_MARKERS):
                break
            if len(line) > 15 and not line.startswith("http"):
                desc_lines.append(line)
            if len("\n".join(desc_lines)) > 800:
                break

    if desc_lines:
        result["description"] = "\n".join(desc_lines)

    return result


def main():
    data_path = os.path.join(os.path.dirname(__file__), "data", "tarot.json")
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    cards = data["cards"]
    total = len(cards)

    for i, card in enumerate(cards):
        name = card["name"]
        upright_url, reversed_url = get_url(card)

        if not upright_url:
            print(f"[{i+1}/{total}] {name} — 无 URL，跳过")
            continue

        print(f"[{i+1}/{total}] {name}")

        # 正位：提取正位关键词 + 牌面描述
        print(f"  正位: {upright_url}")
        html_up = fetch_page(upright_url)
        up_data = parse_card_page(html_up)
        time.sleep(0.8)

        # 逆位：提取逆位关键词
        print(f"  逆位: {reversed_url}")
        html_rev = fetch_page(reversed_url)
        rev_data = parse_card_page(html_rev)
        time.sleep(0.8)

        # 写入新字段，清除旧字段
        card.pop("keywords", None)
        card.pop("scenes", None)
        card.pop("description", None)

        if up_data.get("keywords"):
            card["keywords_upright"] = up_data["keywords"]
        if rev_data.get("keywords"):
            card["keywords_reversed"] = rev_data["keywords"]
        if up_data.get("description"):
            card["description_upright"] = up_data["description"]
        if rev_data.get("description"):
            card["description_reversed"] = rev_data["description"]

        card["source_upright"] = upright_url
        card["source_reversed"] = reversed_url

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n完成！已更新 {data_path}")


if __name__ == "__main__":
    main()
