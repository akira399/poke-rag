"""M0 · 拉取 PokeAPI 全量原始数据到 data/raw/pokeapi/<resource>/<id>.json

设计要点：断点续传（文件已存在则跳过，中断重跑不重复请求）、
线程池并发 + 礼貌限速（公共 API，6 并发 × 0.15s 间隔）、失败指数退避重试。
raw 层只读：响应整包落盘并附带 source_url（供溯源），规范化在 M1 处理。

运行：python scripts/fetch_pokeapi.py            # 全量
      python scripts/fetch_pokeapi.py species     # 只拉某类资源
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tqdm import tqdm

# 本机 CA 证书链被代理中断（UNABLE_TO_VERIFY_LEAF_SIGNATURE），
# 本地开发关闭校验；生产环境必须恢复 TLS_VERIFY = True。
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
TLS_VERIFY = False

API = "https://pokeapi.co/api/v2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_ROOT = os.path.join(ROOT, "data", "raw", "pokeapi")

# 资源清单：M1 卡片管道所需的数据域
RESOURCES = ["pokemon-species", "pokemon", "move", "ability", "item", "evolution-chain"]

WORKERS = 6
REQUEST_INTERVAL = 0.15
RETRIES = 3


def extract_id(url: str) -> int:
    """从 '.../pokemon-species/149/' 这类 URL 提取数字 id。"""
    return int(url.rstrip("/").split("/")[-1])


def list_all(resource: str) -> list[str]:
    """分页取该资源全部条目 URL（PokeAPI 单页上限 100000）。"""
    url = f"{API}/{resource}?limit=100000"
    last_err = None
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, timeout=30, verify=TLS_VERIFY)
            r.raise_for_status()
            return [item["url"] for item in r.json()["results"]]
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"获取 {resource} 资源清单失败: {last_err}")


def fetch_one(session: requests.Session, resource: str, url: str) -> str:
    """下载单条资源；返回状态：ok / skip / 404 / fail。"""
    item_id = extract_id(url)
    out_path = os.path.join(RAW_ROOT, resource, f"{item_id}.json")
    if os.path.exists(out_path):
        return "skip"
    for attempt in range(RETRIES):
        try:
            r = session.get(url, timeout=30, verify=TLS_VERIFY)
            if r.status_code == 404:
                return "404"
            r.raise_for_status()
            payload = r.json()
            payload["source_url"] = url  # 溯源：回答引用出处
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            return "ok"
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return "fail"


def fetch_resource(resource: str) -> dict:
    urls = list_all(resource)
    stats = {"ok": 0, "skip": 0, "404": 0, "fail": 0}
    with tqdm(total=len(urls), desc=f"PokeAPI/{resource}", unit="条") as bar:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            with requests.Session() as session:
                futures = {
                    pool.submit(fetch_one, session, resource, url): url for url in urls
                }
                for fut in as_completed(futures):
                    status = fut.result()
                    stats[status if status in stats else "fail"] += 1
                    bar.update(1)
                    time.sleep(REQUEST_INTERVAL)
    return stats


def write_manifest(resource: str, stats: dict) -> None:
    os.makedirs(RAW_ROOT, exist_ok=True)
    manifest_path = os.path.join(RAW_ROOT, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    manifest[resource] = stats
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resources", nargs="*", default=RESOURCES,
                        help="要拉取的资源名，缺省为全部")
    args = parser.parse_args()
    failed_resources = []
    for resource in args.resources:
        try:
            stats = fetch_resource(resource)
        except Exception as e:
            print(f"⚠️ [{resource}] 拉取失败: {e}（重跑本脚本可续传）")
            failed_resources.append(resource)
            continue
        write_manifest(resource, stats)
        failed = stats.get("fail", 0)
        print(f"[{resource}] 新下载 {stats['ok']} · 跳过 {stats['skip']} · 404 {stats['404']} · 失败 {failed}")
        if failed:
            print(f"⚠️ 失败 {failed} 条，重跑本脚本可续传重试")
    if failed_resources:
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
