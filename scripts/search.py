"""M2 · 命令行检索：输入问题，输出 top-K 卡片。

运行：python scripts/search.py "快龙怕什么"  [--top 5]
      python scripts/search.py            # 交互模式
"""
import sys

sys.path.insert(0, __file__ and sys.path[0] + "/..")

from src.retrieval.index import search  # noqa: E402


def show(query: str, top_k: int) -> None:
    print(f"Q: {query}")
    for rank, (card_id, score) in enumerate(search(query, top_k=top_k), 1):
        print(f"  {rank}. [{score:.4f}] {card_id}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    top_k = 5
    if "--top" in sys.argv:
        top_k = int(sys.argv[sys.argv.index("--top") + 1])
    if not args:
        while True:
            try:
                show(input("> "), top_k)
            except (KeyboardInterrupt, EOFError):
                break
    else:
        show(" ".join(args), top_k)
