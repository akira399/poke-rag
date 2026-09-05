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
from src.generation.llm import stream_chat
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
    def __init__(self):
        self.cfg = load()

    def answer(self, query: str) -> Iterator[dict]:
        """流式回答，元素为 {type: delta|citation|citations|reject|meta}。

        工具路由：招式集合查询（"所有招式/变化招式"）走规则引擎
        （move_query），结果作为事实上下文注入；其余走检索链路。
        检索层内部优雅降级：本地 embedding 不可用时走 BM25-only。
        """
        rag = self.cfg["rag"]
        from src.retrieval import embed as embed_mod

        tool_context = self._try_move_tool(query)
        if tool_context is not None:
            context, citation_map, cards = tool_context
            yield {"type": "citations", "mapping": citation_map, "cards": cards}
            answer_text = ""
            for delta in stream_chat(prompt_mod.build_messages(query, context)):
                answer_text += delta
                yield {"type": "delta", "text": delta}
            yield {"type": "done", "citations_ok": True, "citations_used": []}
            return

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
        # 2) 上下文组装
        context, citation_map = prompt_mod.build_context(fused)
        yield {"type": "citations", "mapping": citation_map,
               "cards": [prompt_mod.load_cards().get(cid) for cid in fused]}
        # 3) 流式生成
        answer_text = ""
        for delta in stream_chat(prompt_mod.build_messages(query, context)):
            answer_text += delta
            yield {"type": "delta", "text": delta}
        # 4) 引用闸：编号必须落在本次知识片段编号内
        valid = set(citation_map.keys())
        used = set(prompt_mod.parse_citations(answer_text))
        yield {"type": "done", "citations_ok": used <= valid, "citations_used": sorted(used)}

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
