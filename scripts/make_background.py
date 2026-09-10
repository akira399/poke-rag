"""生成界面背景图：官方宝可梦立绘 + 高斯虚化 + 渐变蒙层。

用法：python scripts/make_background.py
输出：.streamlit/assets/background.png（1600x1000）

说明：素材来自 PokeAPI 官方立绘仓库（BSD-3），在本地合成后作为界面
背景；虚化与压暗保证与前景文字对比度，观感自然和谐。
"""
from __future__ import annotations

import os
import urllib.request

from PIL import Image, ImageEnhance, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, ".streamlit", "assets", "background.png")
TMP = os.path.join(ROOT, ".streamlit", "assets", "_raw")

SPRITE = ("https://raw.githubusercontent.com/PokeAPI/sprites/master/"
          "sprites/pokemon/other/official-artwork/{id}.png")

# 挑选配色协调的几只（蓝白/暖色系，避免花哨）：水箭龟、拉普拉斯、快龙、七夕青鸟
PICKS = [9, 131, 149, 334]
W, H = 1600, 1000


def fetch(pid: int) -> Image.Image:
    os.makedirs(TMP, exist_ok=True)
    path = os.path.join(TMP, f"{pid}.png")
    if not os.path.exists(path):
        req = urllib.request.Request(SPRITE.format(id=pid),
                                     headers={"User-Agent": "poke-rag/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp, open(path, "wb") as f:
            f.write(resp.read())
    return Image.open(path).convert("RGBA")


def gradient(size: tuple[int, int]) -> Image.Image:
    """从深蓝到靛紫的对角渐变，作为整体色调。"""
    w, h = size
    base = Image.new("RGB", size)
    px = base.load()
    for y in range(h):
        for x in range(0, w, 4):          # 每 4 像素取一次，速度快且够平滑
            t = (x / w * 0.45 + y / h * 0.55)
            r = int(30 + 46 * t)
            g = int(46 + 62 * t)
            b = int(86 + 86 * t)
            for dx in range(4):
                if x + dx < w:
                    px[x + dx, y] = (r, g, b)
    return base


def main() -> None:
    canvas = gradient((W, H)).convert("RGBA")
    # 立绘错落摆放，尺寸不一，形成层次
    layout = [
        (9, (-40, 470), 560),     # 水箭龟，左下（略出画面，营造纵深）
        (131, (1150, 470), 520),  # 拉普拉斯，右下
        (149, (420, -30), 520),   # 快龙，上方偏左
        (334, (1010, 70), 400),   # 七夕青鸟，右上
    ]
    for pid, (x, y), size in layout:
        try:
            art = fetch(pid)
        except Exception as e:          # 取图失败不影响整体生成
            print(f"跳过 {pid}: {e}")
            continue
        art = art.resize((size, size), Image.LANCZOS)
        # 轻微降低不透明度，避免喧宾夺主
        alpha = art.split()[3].point(lambda a: int(a * 0.82))
        art.putalpha(alpha)
        canvas.alpha_composite(art, (x, y))

    # 整体虚化 + 降饱和 + 压暗，保证前景文字清晰
    out = canvas.convert("RGB")
    out = out.filter(ImageFilter.GaussianBlur(14))
    out = ImageEnhance.Color(out).enhance(0.95)
    out = ImageEnhance.Brightness(out).enhance(1.02)

    # 顶部再次压暗，让标题区更稳
    veil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vpx = veil.load()
    for y in range(H):
        a = int(34 * max(0.0, 1 - y / (H * 0.40)))
        for x in range(0, W, 4):
            for dx in range(4):
                if x + dx < W:
                    vpx[x + dx, y] = (6, 10, 24, a)
    out = Image.alpha_composite(out.convert("RGBA"), veil).convert("RGB")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT, "PNG", optimize=True)
    print(f"背景图已生成: {OUT} ({os.path.getsize(OUT) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
