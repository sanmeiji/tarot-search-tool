"""
下载所有 78 张 Rider-Waite-Smith 塔罗牌图片到 static/images/
运行：python download_images.py
"""
import os
import time
import requests

BASE = "https://raw.githubusercontent.com/metabismuth/tarot-json/master/cards"
OUT  = os.path.join(os.path.dirname(__file__), "static", "images")
os.makedirs(OUT, exist_ok=True)

# 大阿卡那 m00~m21
MAJOR = [f"m{str(i).zfill(2)}" for i in range(22)]

# 小阿卡那
MINOR_SUITS  = ["c", "w", "s", "p"]   # 圣杯 权杖 宝剑 星币
MINOR_NUMS   = [str(i).zfill(2) for i in range(1, 15)]  # 01~14
MINOR = [f"{s}{n}" for s in MINOR_SUITS for n in MINOR_NUMS]

ALL = MAJOR + MINOR

HEADERS = {"User-Agent": "Mozilla/5.0"}

total = len(ALL)
skipped = 0
downloaded = 0

for i, name in enumerate(ALL, 1):
    fname = f"{name}.jpg"
    dest  = os.path.join(OUT, fname)
    if os.path.exists(dest):
        skipped += 1
        print(f"[{i}/{total}] {fname} 已存在，跳过")
        continue
    url = f"{BASE}/{fname}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        downloaded += 1
        print(f"[{i}/{total}] {fname} ({len(r.content)//1024} KB)")
    except Exception as e:
        print(f"[{i}/{total}] !! {fname} 失败: {e}")
    time.sleep(0.3)

print(f"\n完成：下载 {downloaded} 张，跳过 {skipped} 张，共 {total} 张")
print(f"图片目录：{OUT}")
