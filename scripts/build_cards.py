"""M1 · 知识卡片生成入口：raw 数据 -> data/cards/*.jsonl

运行：python scripts/build_cards.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.pipeline.aliases import build_aliases  # noqa: E402
from src.pipeline.build_cards import (  # noqa: E402
    build_meta_cards,
    render_ability_card,
    render_item_card,
    render_move_card,
    render_pokemon_card,
    top_moves_text,
)
from src.pipeline.normalize import (  # noqa: E402
    normalize_ability,
    normalize_item,
    normalize_move,
    normalize_pokemon,
    normalize_species,
)

CARDS_DIR = os.path.join(ROOT, "data", "cards")
RAW_POKEAPI = os.path.join(ROOT, "data", "raw", "pokeapi")


def _iter_ids(resource: str):
    folder = os.path.join(RAW_POKEAPI, resource)
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json") and name[:-5].isdigit():
            yield int(name[:-5])


def _write_jsonl(filename: str, cards: list[dict]) -> None:
    os.makedirs(CARDS_DIR, exist_ok=True)
    with open(os.path.join(CARDS_DIR, filename), "w", encoding="utf-8") as f:
        for card in cards:
            f.write(json.dumps(card, ensure_ascii=False) + "\n")


def build_all() -> dict[str, int]:
    aliases = build_aliases()
    # 先构建招式/特性/道具卡（pokemon 卡的「可学习招式」段需要招式中文名）
    move_cards = [render_move_card(normalize_move(i)) for i in _iter_ids("move")]
    ability_cards = [render_ability_card(normalize_ability(i)) for i in _iter_ids("ability")]
    item_cards = [render_item_card(normalize_item(i)) for i in _iter_ids("item")]
    _write_jsonl("move.jsonl", move_cards)
    _write_jsonl("ability.jsonl", ability_cards)
    _write_jsonl("item.jsonl", item_cards)

    moves_zh = {}
    for card in move_cards:
        moves_zh[card["title_en"].lower().replace(" ", "").replace("-", "")] = card["title_zh"]

    # 宝可梦卡片 = species 与 pokemon 按 id 对齐（1..1025 物种，pokemon 含形态）
    pokemon_cards = []
    for pk_id in sorted(_iter_ids("pokemon")):
        # 仅取「物种本体」：PokeAPI pokemon 目录含形态（10000+ 号段），
        # 卡片以物种统一命名，形态数据后续作为能力增强
        if pk_id < 10000:
            sp = normalize_species(pk_id)  # species id 与本体 pokemon id 对齐
            pk = normalize_pokemon(pk_id)
            card = render_pokemon_card(sp, pk, moves_text=top_moves_text(sp.name_en, moves_zh))
            card["aliases"] = [a for a in (card["aliases"] + [sp.name_zh, sp.name_en]) if a]
            pokemon_cards.append(card)

    _write_jsonl("pokemon.jsonl", pokemon_cards)
    meta_cards = build_meta_cards()
    _write_jsonl("meta.jsonl", meta_cards)

    # 别名表沉淀：检索层直接用
    with open(os.path.join(CARDS_DIR, "aliases.json"), "w", encoding="utf-8") as f:
        json.dump(aliases, f, ensure_ascii=False, indent=2)

    return {
        "pokemon": len(pokemon_cards),
        "move": len(move_cards),
        "ability": len(ability_cards),
        "item": len(item_cards),
        "meta": len(meta_cards),
        "aliases": len(aliases),
    }


if __name__ == "__main__":
    for k, v in build_all().items():
        print(f"{k}: {v}")
