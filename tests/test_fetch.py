"""M0 采集脚本的纯函数单测（不依赖网络）。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.fetch_pokeapi import extract_id
from scripts.fetch_smogon import parse_chaos_index, parse_index_html


class TestExtractId:
    def test_normal_url(self):
        assert extract_id("https://pokeapi.co/api/v2/pokemon-species/149/") == 149

    def test_multi_digit(self):
        assert extract_id("https://pokeapi.co/api/v2/move/1119/") == 1119

    def test_no_trailing_slash(self):
        assert extract_id("https://pokeapi.co/api/v2/ability/1") == 1


class TestSmogonIndex:
    def test_parse_index_html_returns_sorted_months(self):
        html = """<a href="2026-06/">2026-06</a><a href="2026-08/">2026-08</a><a href="2026-07/">2026-07</a>"""
        assert parse_index_html(html) == ["2026-06", "2026-07", "2026-08"]

    def test_parse_chaos_matches_gz_and_generation(self):
        html = """<a href="gen9ou-1500.json.gz">gen9ou-1500</a>
                  <a href="gen9ubers-1500.json.gz">gen9ubers</a>
                  <a href="gen8doubles-1500.json.gz">gen8doubles</a>
                  <a href="gen1ou-1500.json.gz">gen1ou</a>
                  <a href="gen9ou-0.json.gz">gen9ou-0</a>"""
        files = parse_chaos_index(html)
        assert "gen9ou-1500.json.gz" in files
        assert "gen9ubers-1500.json.gz" in files
        assert "gen8doubles-1500.json.gz" in files
        assert "gen1ou-1500.json.gz" not in files  # 世代白名单外被过滤
        assert "gen9ou-0.json.gz" not in files     # 仅取 -1500 样本
