"""M3 · CLI 端到端问答：python scripts/rag_chat.py "快龙怕什么？"

演示流式输出 + 引用 + 拒答（不传参数进入交互模式）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generation.rag import RAGEngine  # noqa: E402


def chat(query: str) -> None:
    print(f"Q: {query}")
    engine = RAGEngine()
    citations = {}
    for event in engine.answer(query):
        if event["type"] == "reject":
            print("A: 知识库中未找到相关信息。")
            return
        if event["type"] == "citations":
            citations = event["mapping"]
            continue
        if event["type"] == "delta":
            print(event["text"], end="", flush=True)
            continue
        if event["type"] == "done":
            print()
            if not event["citations_ok"]:
                print(f"(引用校验警告: {event['citations_used']} 不在知识片段内)")
    print("来源:", "; ".join(citations.values()))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        while True:
            try:
                chat(input("> "))
            except (KeyboardInterrupt, EOFError):
                break
    else:
        chat(" ".join(args))
