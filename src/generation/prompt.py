"""M3 · 提示词与上下文组装（RAG 生成层的"闸门"之一）。

系统提示词约束三件事：只依据知识片段、答案必须带引用编号、
知识未覆盖时明确说不知道（不编造）。展示的上下文卡片按
[1][2][3]… 编号，与检索卡片一一对应（引用溯源）。
"""
from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CARDS_DIR = os.path.join(_ROOT, "data", "cards")


SYSTEM_PROMPT = (
    "你是一个精通宝可梦对战的问答助手。回答规则：\n"
    "1. 只能依据提供的知识片段回答，不得使用片段没有的信息；\n"
    "2. 引用信息时在句末标注来源编号 [1][2]...，编号必须与知识片段一致；\n"
    "3. 知识片段不足以回答时，直接说明「知识库中未找到相关信息」，不要猜测；\n"
    "4. 用中文回答，简洁准确；涉及数字（威力、种族值、伤害）以片段数据为准。"
)


def load_cards() -> dict[str, dict]:
    """card_id -> card（引用编号映射时的数据源）。"""
    cards: dict[str, dict] = {}
    for name in ("pokemon", "move", "ability", "item"):
        path = os.path.join(CARDS_DIR, f"{name}.jsonl")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                card = json.loads(line)
                cards[card["card_id"]] = card
    return cards


def build_context(card_ids: list[str]) -> tuple[str, str]:
    """把选中卡片渲染成带编号的知识片段。

    返回 (context_text, citation_map)：citation_map 把 [1] 映射回卡片
    （供引用校验与前端展开来源）。
    """
    cards = load_cards()
    lines = []
    mapping: dict[str, str] = {}
    for i, cid in enumerate(card_ids, 1):
        card = cards.get(cid)
        if not card:
            continue
        lines.append(f"[{i}] {card.get('content_zh', '')}")
        mapping[str(i)] = cid
    return "\n".join(lines), mapping


def build_messages(query: str, context: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"知识片段：\n{context}\n\n问题：{query}"},
    ]


def parse_citations(answer: str) -> list[str]:
    """从答案里抽取引用编号（[1]、[2] 等）。"""
    import re

    return re.findall(r"\[(\d+)\]", answer)
