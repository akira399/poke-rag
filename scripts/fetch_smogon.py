"""M0 · 下载 Smogon 月度使用率统计（chaos JSON.gz）到 data/raw/smogon/stats/

只取最新月份的 gen8/gen9 常用分级（ou/ubers/uu/ru/nu/pu/doubles）的 -1500
分段统计。chao 目录文件为 gzip 压缩的 JSON（.json.gz），下载后解压，
压缩包保留在 raw 层。

运行：python scripts/fetch_smogon.py   # 自动取最新月份
"""
import gzip
import json
import os
import re
import sys

import requests

# 本机 CA 证书链被代理中断，本地开发关闭校验；生产环境恢复 TLS_VERIFY = True。
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
TLS_VERIFY = False

SMOGON_BASE = "https://www.smogon.com/stats"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "raw", "smogon", "stats")

# 第 8/9 世代常用分级的 -1500 分段（Smogon 标准参考样本）
TARGET_RE = re.compile(r"gen(?:8|9)(?:ou|ubers|uu|ru|nu|pu|doubles)-1500\.json\.gz")


def parse_index_html(html: str) -> list[str]:
    """从月份目录页提取形如 2026-08 的目录名（已排序去重）。"""
    months = re.findall(r"(\d{4}-\d{2})", html)
    return sorted(set(months))


def parse_chaos_index(html: str) -> list[str]:
    """按「世代 + tier + 分段」白名单提取 .json.gz 文件名（去重保序）。"""
    return sorted(set(TARGET_RE.findall(html)))


def main() -> None:
    root_resp = requests.get(f"{SMOGON_BASE}/", timeout=30, verify=TLS_VERIFY)
    root_resp.raise_for_status()
    months = parse_index_html(root_resp.text)
    if not months:
        print("⚠️ 未解析到月份目录，请检查 Smogon 站点结构")
        sys.exit(1)
    latest = months[-1]
    print(f"最新统计月份: {latest}")

    chaos_url = f"{SMOGON_BASE}/{latest}/chaos/"
    chaos_resp = requests.get(chaos_url, timeout=30, verify=TLS_VERIFY)
    chaos_resp.raise_for_status()
    files = parse_chaos_index(chaos_resp.text)
    if not files:
        print("⚠️ chaos 目录未找到目标 JSON，站点结构可能变更")
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)
    downloaded = []
    for name in files:
        gz_path = os.path.join(OUT_DIR, name)
        if os.path.exists(gz_path):
            continue
        r = requests.get(f"{chaos_url}{name}", timeout=60, verify=TLS_VERIFY)
        if not r.ok:
            print(f"跳过 {name} (HTTP {r.status_code})")
            continue
        with open(gz_path, "wb") as f:
            f.write(r.content)
        json_name = name[: -len(".gz")]
        with gzip.open(gz_path, "rt", encoding="utf-8") as f_in, \
             open(os.path.join(OUT_DIR, json_name), "w", encoding="utf-8") as f_out:
            json.dump(json.load(f_in), f_out, ensure_ascii=False)
        downloaded.append(name)
    print(f"下载完成 {len(downloaded)} 个文件到 {OUT_DIR}")
    for name in downloaded:
        print("  -", name)


if __name__ == "__main__":
    main()
