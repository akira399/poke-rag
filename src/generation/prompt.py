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
    "4. 用中文回答，简洁准确；涉及数字（威力、种族值、伤害）以片段数据为准；\n"
    "5. 用户未指明游戏或环境时，默认按《宝可梦冠军》（Pokémon Champions）"
    "对战游戏的环境回答：知识片段同时含主线游戏与冠军游戏数据时，优先采用"
    "冠军游戏的数据；若问题明确提到其他游戏或环境（如《朱／紫》、Gen9 OU、"
    "主线剧情），则按对应环境回答。"
)


def load_cards() -> dict[str, dict]:
    """card_id -> card（引用编号映射时的数据源）。

    必须覆盖检索语料的全部卡片类型：漏一类，该类卡片会在上下文组装时
    被静默丢弃，模型拿到空上下文只能拒答（llm-eval 评测发现的实证）。
    """
    cards: dict[str, dict] = {}
    for name in ("pokemon", "form", "move", "ability", "item", "meta", "typechart", "champion", "game"):
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


def normalize_sections(answer: str) -> str:
    """保证「情形 N」「★ 总体结论」各自成段（确定性排版兜底）。

    LLM 对伤害计算极端情形的输出不稳定：有时用列表（正常分段），有时照抄
    上下文的单换行——单换行在 Markdown 里渲染为同一段落，三个情形会挤成一
    大坨。此处在渲染前强制分段，不依赖模型自觉。

    只处理伤害计算特有的标记（情形 N｜ / ★ 总体结论），误伤面极小。
    """
    import re

    # 先补"句中紧贴"的情况（句号/分号/引用标记后直接跟 情形 N，无换行）
    answer = re.sub(r"(?<=[。；;！？\]])\s+(?=情形\s*\d[｜|])", "\n\n", answer)
    answer = re.sub(r"(?<=[。；;！？\]])\s+(?=★\s*总体结论)", "\n\n", answer)
    # 再把已有换行（单/多）统一规范化为恰好一个空行（幂等）
    answer = re.sub(r"\n+(?=情形\s*\d[｜|])", "\n\n", answer)
    answer = re.sub(r"\n+(?=★\s*总体结论)", "\n\n", answer)
    return answer


def linkify_citations(answer: str, cards_by_no: dict[str, dict]) -> str:
    """把答案里的 [n] 变成可点击链接（指向来源 URL），供用户点击查证。

    cards_by_no: {编号: 卡片}（source.url 为权威来源页面，如 PokeAPI）。
    无来源 URL 的编号保持原样（如规则查询结果）。
    """
    import re

    def repl(match):
        n = match.group(1)
        card = cards_by_no.get(n) or {}
        url = (card.get("source") or {}).get("url")
        return f"[[{n}]]({url})" if url else match.group(0)

    return re.sub(r"\[(\d+)\]", repl, answer)
