"""M3 · RAG 问答编排：检索 -> 置信度闸 -> 上下文组装 -> 流式生成。

四道反幻觉闸（方案 §6.2）在本层落三道：
1. 检索闸：top-1 相似度低于阈值（cosine 距离过大）→ 直接拒答；
2. 提示词闸：系统提示词约束（prompt.py）；
3. 引用闸：答案生成的引用编号必须是本次检索到的卡片（后校验）。
"""
from __future__ import annotations

from collections.abc import Iterator

from src.config import load
from src.generation import prompt as prompt_mod
from src.retrieval.index import search


class Retriever:
    """按配置取 top_k_retrieve 的检索结果与距离（供置信度判断）。"""

    def retrieve(self, query: str, top_k: int) -> dict:
        from src.retrieval.embed import embed_query
        from src.retrieval.index import _collection

        return _collection().query(
            query_embeddings=[embed_query(query)],
            n_results=top_k,
            include=["ids", "distances"],
        )


class RAGEngine:
    def __init__(self, llm_cfg: dict | None = None):
        # llm_cfg：会话级覆盖（云端多用户各自填 API Key），为 None 时用全局配置。
        # 注意 self._llm_cfg 在两种模式下都非空（站点模式填的是全局配置），
        # 因此不能靠"有没有 key"判断模式，必须记住是否由用户提供。
        self._user_llm = bool(llm_cfg)
        self.cfg = load({"llm": llm_cfg} if llm_cfg else None)
        self._llm_cfg = self.cfg["llm"]

    def answer(self, query: str) -> Iterator[dict]:
        """流式回答，元素为 {type: delta|citation|citations|reject|meta}。

        工具路由：招式集合查询（"所有招式/变化招式"）走规则引擎
        （move_query），结果作为事实上下文注入；其余走检索链路。
        检索层内部优雅降级：本地 embedding 不可用时走 BM25-only。
        """
        rag = self.cfg["rag"]
        from src.retrieval import embed as embed_mod

        tool_context, route_detail = self._try_rule_tool(query)
        if tool_context is not None:
            context, citation_map, cards = tool_context
            yield {"type": "route", "path": "tool", "detail": route_detail}
            yield {"type": "citations", "mapping": citation_map, "cards": cards}
            answer_text = ""
            for event in self._generate(prompt_mod.build_messages(query, context)):
                if event["type"] == "delta":
                    answer_text += event["text"]
                yield event
            yield {"type": "done", "citations_ok": True, "citations_used": []}
            return

        yield {"type": "route", "path": "rag", "detail": "知识库检索 → 流式生成"}

        if rag.get("use_dense", False) and embed_mod.embedding_available():
            from src.retrieval.index import _collection
            from src.retrieval.embed import embed_query
            from src.retrieval.query_expand import expand

            raw = _collection().query(
                query_embeddings=[embed_query(expand(query))],
                n_results=rag["top_k_retrieve"],
            )
            distances = list(raw["distances"][0])
            if not distances or distances[0] > rag["reject_distance_threshold"]:
                yield {"type": "reject"}
                return

        fused = [cid for cid, _ in search(query, top_k=rag["top_k_answer"])]
        if not fused:
            yield {"type": "reject"}
            return
        all_cards = prompt_mod.load_cards()
        yield {"type": "retrieval", "hits": [
            {"card_id": cid,
             "title_zh": (all_cards.get(cid) or {}).get("title_zh", cid),
             "type": (all_cards.get(cid) or {}).get("type", "")}
            for cid in fused
        ]}
        # 2) 上下文组装
        context, citation_map = prompt_mod.build_context(fused)
        yield {"type": "citations", "mapping": citation_map,
               # 按映射对齐：检索命中但组装层缺失的卡不在映射里，
               # 混入会错位并让上层拿到 None（线上事故 2026-09-12）
               "cards": [all_cards.get(cid) for cid in citation_map.values()]}
        # 3) 流式生成
        answer_text = ""
        for event in self._generate(prompt_mod.build_messages(query, context)):
            if event["type"] == "delta":
                answer_text += event["text"]
            yield event
        # 4) 引用闸：编号必须落在本次知识片段编号内
        valid = set(citation_map.keys())
        used = set(prompt_mod.parse_citations(answer_text))
        yield {"type": "done", "citations_ok": used <= valid, "citations_used": sorted(used)}

    def _generate(self, messages: list[dict]) -> Iterator[dict]:
        """调模型并转发事件：reasoning（思考过程）与 delta（答案碎片）。

        站点免费模式下走候选链——主模型被限流(429)/超时时自动切备用模型
        （见 fallback.py）；用户自带 Key 时只用自己的 Key，不降级。
        """
        from src.generation.fallback import stream_with_fallback

        for event in stream_with_fallback(self.cfg, messages, self._user_llm):
            etype = event["type"]
            if etype == "reasoning":
                yield {"type": "reasoning", "text": event["text"]}
            elif etype == "content":
                yield {"type": "delta", "text": event["text"]}
            elif etype == "fallback":
                yield {"type": "fallback", "detail": event["detail"]}
            elif etype == "all_failed":
                yield {"type": "error", "detail": event["detail"]}

    def _try_rule_tool(self, query: str):
        """规则工具分发：伤害计算优先，其次招式集合查询。

        返回 ((context, citation_map, cards), 路由说明) 或 (None, "")。
        """
        from src.rules.damage_query import try_build_context

        dmg = try_build_context(query)
        if dmg is not None:
            card = {"card_id": "rule:damage", "type": "rule",
                    "title_zh": "伤害计算（规则引擎）", "title_en": "damage-calc",
                    "content_zh": "本结果由伤害计算引擎产出（与官方 @smogon/calc 对拍一致）",
                    "source": {"provider": "smogon-calc",
                               "url": "https://github.com/smogon/damage-calc"}}
            return (dmg, {"1": "rule:damage"}, [card]),                 "伤害计算 → 规则引擎（@smogon/calc 对拍一致的公式）"

        move_ctx = self._try_move_tool(query)
        if move_ctx is not None:
            return move_ctx, "招式集合查询 → 规则引擎（learnsets + moves）"
        return None, ""

    def _try_move_tool(self, query: str):
        """招式集合查询（规则工具）。命中返回 (context, citation_map, cards)，否则 None。"""
        from src.rules.move_query import detect_move_query, format_moves, list_moves
        from src.retrieval.query_expand import _load_aliases

        species_en, hit = detect_move_query(query, _load_aliases())
        if not hit:
            return None
        result = list_moves(species_en)
        if not result:
            return None
        card = {"card_id": "rule:move_query", "type": "rule",
                "title_zh": f"{species_en} 招式规则查询",
                "title_en": species_en, "content_zh": ""}
        # 用户明确要「所有」时全列，否则默认列前 40 防上下文过长
        full = any(k in query for k in ("所有", "全部"))
        context = format_moves(species_en, result, limit_all=0 if full else 40)
        return context, {"1": "rule:move_query"}, [card]
