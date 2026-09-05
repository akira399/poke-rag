"""M1 · 规范化层：raw PokeAPI JSON -> 归一化的实体结构

每个 normalize 函数都是纯函数：输入 raw 文件内容，输出精简实体 dict。
只保留卡片管道和规则引擎需要的字段，所有字段带官方来源可追溯。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "data", "raw", "pokeapi")

ZH = "zh-hans"
EN = "en"

# PokeAPI 图鉴描述有 8 个中文版本，按世代新旧排序，优先取新世代
_FLAVOR_ORDER = ["sword", "shield", "ultra-sun", "ultra-moon", "sun", "moon",
                 "lets-go-pikachu", "lets-go-eevee"]


@dataclass
class Species:
    id: int
    name_en: str
    name_zh: str
    flavor_zh: str = ""
    generation: str = ""
    egg_groups: list[str] = field(default_factory=list)
    evolution_chain_id: int = 0
    source_url: str = ""


@dataclass
class Pokemon:
    id: int
    name_en: str
    name_zh: str
    types: list[str]
    base_stats: dict
    abilities: list[str]
    heightm: float
    weightkg: float


@dataclass
class Move:
    id: int
    name_en: str
    name_zh: str
    move_type: str
    power: int | None
    accuracy: int | None
    pp: int | None
    effect_zh: str = ""
    effect_en: str = ""


@dataclass
class Ability:
    id: int
    name_en: str
    name_zh: str
    effect_en: str = ""
    effect_zh: str = ""


@dataclass
class Item:
    id: int
    name_en: str
    name_zh: str
    effect_en: str = ""


def _name(data: dict, lang: str) -> str:
    for n in data.get("names", []):
        if n["language"]["name"] == lang:
            return n["name"]
    return data.get("name", "")


def _load(resource: str, item_id: int) -> dict:
    with open(os.path.join(RAW, resource, f"{item_id}.json"), encoding="utf-8") as f:
        return json.load(f)


def normalize_species(item_id: int) -> Species:
    d = _load("pokemon-species", item_id)
    flavor = ""
    by_version = {f["version"]["name"]: f["flavor_text"]
                  for f in d.get("flavor_text_entries", [])
                  if f["language"]["name"] == ZH}
    for version in _FLAVOR_ORDER:
        if version in by_version:
            flavor = by_version[version].replace("\n", " ").replace("\f", " ").strip()
            break
    chain_id = 0
    if d.get("evolution_chain"):
        chain_id = int(d["evolution_chain"]["url"].rstrip("/").split("/")[-1])
    return Species(
        id=d["id"],
        name_en=_name(d, EN),
        name_zh=_name(d, ZH),
        flavor_zh=flavor,
        generation=d.get("generation", {}).get("name", ""),
        egg_groups=[g["name"] for g in d.get("egg_groups", [])],
        evolution_chain_id=chain_id,
        source_url=d.get("source_url", ""),
    )


def normalize_pokemon(item_id: int) -> Pokemon:
    d = _load("pokemon", item_id)
    # 注意：/pokemon 资源不含 names 字段（官方多语言名只有 /pokemon-species 提供），
    # 中文名由 species 侧提供，卡片层做对齐。
    return Pokemon(
        id=d["id"],
        name_en=d["name"],
        name_zh=d["name"],
        types=[t["type"]["name"] for t in d.get("types", [])],
        base_stats={s["stat"]["name"]: s["base_stat"] for s in d.get("stats", [])},
        abilities=[a["ability"]["name"] for a in d.get("abilities", [])],
        heightm=d.get("height", 0) / 10,
        weightkg=d.get("weight", 0) / 10,
    )


def normalize_move(item_id: int) -> Move:
    d = _load("move", item_id)
    effects = [e for e in d.get("effect_entries", [])]
    return Move(
        id=d["id"],
        name_en=d["name"],
        name_zh=_name(d, ZH),
        move_type=d.get("type", {}).get("name", ""),
        power=d.get("power"),
        accuracy=d.get("accuracy"),
        pp=d.get("pp"),
        effect_en=next((e["effect"] for e in effects if e["language"]["name"] == EN), ""),
        effect_zh=next((e["effect"] for e in effects if e["language"]["name"] == ZH), ""),
    )


def normalize_ability(item_id: int) -> Ability:
    d = _load("ability", item_id)
    entries = d.get("effect_entries", [])
    return Ability(
        id=d["id"],
        name_en=d["name"],
        name_zh=_name(d, ZH),
        effect_en=next((e["effect"] for e in entries if e["language"]["name"] == EN), ""),
        effect_zh=next((e["effect"] for e in entries if e["language"]["name"] == ZH), ""),
    )


def normalize_item(item_id: int) -> Item:
    d = _load("item", item_id)
    entries = d.get("effect_entries", [])
    return Item(
        id=d["id"],
        name_en=d["name"],
        name_zh=_name(d, ZH),
        effect_en=next((e["effect"] for e in entries if e["language"]["name"] == EN), ""),
    )
