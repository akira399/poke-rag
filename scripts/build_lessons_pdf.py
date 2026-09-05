"""把六篇讲解合订生成 PDF（markdown → HTML → Edge 无头打印）。

输出：docs/Poke-RAG-项目详解.pdf（gitignore，本地学习用）
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LESSONS = [
    ("02-M0-讲解.md", "第一课 · 数据管道"),
    ("04-M1-讲解.md", "第二课 · 知识卡片"),
    ("05-M2-讲解.md", "第三课 · 检索层"),
    ("06-M3-讲解.md", "第四课 · 生成层"),
    ("07-M4-讲解.md", "第五课 · 门户与规则引擎"),
    ("08-M5-讲解.md", "第六课 · 深度调优"),
]

CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
       font-size: 10.5pt; line-height: 1.85; color: #1f2328; margin: 0; }
h1 { font-size: 17pt; border-bottom: 3px solid #d73a49; padding-bottom: 8px;
     margin: 0 0 18px; page-break-before: always; }
h1.first { page-break-before: avoid; }
h2 { font-size: 13.5pt; border-left: 5px solid #d73a49; padding-left: 10px;
     margin: 26px 0 12px; }
h3 { font-size: 11.5pt; margin: 20px 0 10px; }
blockquote { background: #fff8e6; border-left: 4px solid #f0b429;
             margin: 12px 0; padding: 10px 14px; color: #5a4a1f; }
pre { background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 6px;
      padding: 12px 14px; overflow-x: hidden; white-space: pre-wrap;
      word-break: break-all; font-size: 9pt; line-height: 1.55;
      font-family: Consolas, "Cascadia Mono", "Microsoft YaHei", monospace; }
code { font-family: Consolas, "Cascadia Mono", monospace; background: #f0f1f3;
       padding: 1px 5px; border-radius: 3px; font-size: 9.5pt; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 9.5pt; }
th, td { border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; }
th { background: #f6f8fa; }
.cover { text-align: center; padding-top: 160px; page-break-after: always; }
.cover h1 { border: none; font-size: 30pt; page-break-before: avoid; }
.cover .sub { font-size: 14pt; color: #555; margin: 14px 0; }
.cover .meta { color: #888; margin-top: 60px; font-size: 11pt; }
.toc { page-break-after: always; }
.toc h1 { page-break-before: avoid; }
.toc li { font-size: 12pt; margin: 10px 0; }
.toc .l2 { font-size: 10.5pt; color: #666; margin-left: 26px; list-style: none; }
hr { border: none; border-top: 1px solid #e1e4e8; margin: 22px 0; }
"""


def build_html() -> str:
    import markdown

    parts = [f"""<div class="cover">
<h1>Poke-RAG 项目详解</h1>
<div class="sub">宝可梦对战知识库问答系统 · 从零开始的六课</div>
<div class="sub" style="font-size:11.5pt">数据管道 · 知识卡片 · 检索 · 生成 · 门户与规则引擎 · 调优验证</div>
<div class="meta">配套开源仓库：github.com/akira399/poke-rag<br>
每课含：常识铺垫（C 语言桥接） · 真实代码逐段精讲 · 现场事故复盘 · 自测题</div>
</div>
<div class="toc"><h1>目录</h1><ol>"""]
    for _, title in LESSONS:
        parts.append(f"<li>{title}</li>")
    parts.append("""</ol>
<div style="margin-top:30px;color:#666;font-size:10.5pt">
学习建议：每课按「常识铺垫 → 代码精讲 → 实际操作 → 自测」的顺序读；
自测答不出来就回到对应小节重读；所有代码都真实存在于仓库中，
建议边读边打开源文件对照。</div></div>""")

    for fname, _ in LESSONS:
        path = os.path.join(ROOT, "docs", fname)
        with open(path, encoding="utf-8") as f:
            md = f.read()
        html = markdown.markdown(md, extensions=["tables", "fenced_code", "nl2br"])
        parts.append(html)
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<style>{CSS}</style></head><body>{''.join(parts)}</body></html>"""


def main() -> int:
    html_path = os.path.join(ROOT, "docs", "_lessons.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html())

    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    out_pdf = os.path.join(ROOT, "docs", "Poke-RAG-项目详解.pdf")
    subprocess.run([
        edge,
        f"--headless=old",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={out_pdf}",
        "file:///" + html_path.replace("\\", "/"),
    ], check=True, timeout=120)
    size = os.path.getsize(out_pdf)
    print(f"PDF 生成成功: {out_pdf} ({size/1024:.0f} KB)")
    os.remove(html_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
