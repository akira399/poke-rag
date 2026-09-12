"""M4 · FastAPI 后端：RAG 问答（SSE 流式）/ 检索调试 / 模型设置。

启动：python scripts/serve.py            （默认 http://127.0.0.1:8765）
"""
from __future__ import annotations

import json
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config as config_mod  # noqa: E402
from src.generation.rag import RAGEngine  # noqa: E402
from src.retrieval.index import search  # noqa: E402

app = FastAPI(title="Poke-RAG")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class ChatRequest(BaseModel):
    query: str


class SettingsRequest(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    temperature: float | None = None


@app.get("/api/health")
def health():
    return {"status": "ok", "model": config_mod.load()["llm"]["model"]}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """SSE：events 依次为 citations/delta* /done 或 reject。"""
    def gen():
        try:
            for event in RAGEngine().answer(req.query):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            # 流中途异常（如不可重试的模型错误）不应静默断连，转成可读事件
            err = {"type": "error",
                   "detail": f"服务异常（{type(e).__name__}），请稍后重试。"}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/search")
def search_api(q: str, top_k: int = 5):
    from src.retrieval.index import _load_cards

    cards = {c["card_id"]: c for c in _load_cards()}
    hits = search(q, top_k=top_k)
    return {
        "query": q,
        "hits": [
            {"card_id": cid, "score": round(score, 4),
             "title_zh": cards.get(cid, {}).get("title_zh", ""),
             "content_zh": cards.get(cid, {}).get("content_zh", "")[:200]}
            for cid, score in hits
        ],
    }


@app.get("/api/settings")
def get_settings():
    llm = config_mod.load()["llm"]
    return {
        "base_url": llm["base_url"],
        "model": llm["model"],
        "api_key_masked": config_mod.masked_key(llm["api_key"]),
    }


@app.post("/api/settings")
def set_settings(req: SettingsRequest):
    values = {k: v for k, v in req.model_dump().items() if v is not None}
    config_mod.save("llm", values)
    return get_settings()


def main():
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
