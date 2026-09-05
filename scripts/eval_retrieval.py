"""M2/M5 · 检索评测（70 问）+ Meta 评测（10 问）。

题目按「要答出的卡片标题」记录；运行前要求索引已构建。
目标（方案 §8）：top-3 ≥ 80%、top-1 ≥ 55%。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.retrieval.index import search  # noqa: E402

CARDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cards")

# 每问：q=自然语言问题，title_en=期望命中的卡片（按英文标题解析）
QUESTIONS = [
    # —— 图鉴（10）——
    {"q": "快龙是什么属性的宝可梦？", "title_en": "dragonite"},
    {"q": "皮卡丘有什么特性？", "title_en": "pikachu"},
    {"q": "喷火龙的种族值是多少？", "title_en": "charizard"},
    {"q": "耿鬼的图鉴描述是什么？", "title_en": "gengar"},
    {"q": "卡比兽有多重？", "title_en": "snorlax"},
    {"q": "烈咬陆鲨是什么属性？", "title_en": "garchomp"},
    {"q": "仙子伊布是什么属性？", "title_en": "sylveon"},
    {"q": "路卡利欧是什么属性？", "title_en": "lucario"},
    {"q": "快龙有没有多鳞特性？", "title_en": "dragonite"},
    {"q": "班基拉斯是什么属性？", "title_en": "tyranitar"},
    # —— 招式（8）——
    {"q": "十万伏特的威力是多少？", "title_en": "thunderbolt"},
    {"q": "地震招式是什么属性？", "title_en": "earthquake"},
    {"q": "冲浪的命中率是多少？", "title_en": "surf"},
    {"q": "冷冻光线是什么属性的招式？", "title_en": "ice-beam"},
    {"q": "龙之舞有什么效果？", "title_en": "dragon-dance"},
    {"q": "剑舞的效果是什么？", "title_en": "swords-dance"},
    {"q": "暗影球的威力是多少？", "title_en": "shadow-ball"},
    {"q": "破坏死光是什么属性的招式？", "title_en": "hyper-beam"},
    # —— 特性（6）——
    {"q": "硬壳盔甲有什么效果？", "title_en": "shell-armor"},
    {"q": "什么特性让宝可梦不会受到会心一击？", "title_en": "shell-armor"},
    {"q": "多鳞的效果是什么？", "title_en": "multiscale"},
    {"q": "威吓有什么效果？", "title_en": "intimidate"},
    {"q": "加速特性的效果是什么？", "title_en": "speed-boost"},
    {"q": "结实特性的效果是什么？", "title_en": "sturdy"},
    # —— 道具（6）——
    {"q": "大师球的效果是什么？", "title_en": "master-ball"},
    {"q": "气势披带有什么效果？", "title_en": "focus-sash"},
    {"q": "讲究围巾的效果是什么？", "title_en": "choice-scarf"},
    {"q": "剩饭有什么效果？", "title_en": "leftovers"},
    {"q": "生命宝珠的效果是什么？", "title_en": "life-orb"},
    {"q": "进化奇石是什么效果？", "title_en": "eviolite"},
    # —— 图鉴扩展（10）——
    {"q": "拉普拉斯是什么属性？", "title_en": "lapras"},
    {"q": "巨钳螳螂是什么属性？", "title_en": "scizor"},
    {"q": "火神蛾的种族值是多少？", "title_en": "volcarona"},
    {"q": "三首恶龙是什么属性？", "title_en": "hydreigon"},
    {"q": "超坏星有什么特性？", "title_en": "toxapex"},
    {"q": "钢铠鸦是什么属性？", "title_en": "corviknight"},
    {"q": "多龙巴鲁托是什么属性？", "title_en": "dragapult"},
    {"q": "暴露菇有什么特性？", "title_en": "amoonguss"},
    {"q": "暴鲤龙怕什么属性？", "title_en": "gyarados"},
    {"q": "耿鬼的种族值是多少？", "title_en": "gengar"},
    # —— 关联查询（宝可梦→招式榜）——
    {"q": "啪嚓海胆威力最大的技能是什么？", "title_en": "pincurchin"},
    {"q": "快龙会哪些高威力招式？", "title_en": "dragonite"},
    # —— 招式扩展（12）——
    {"q": "岩崩是什么属性的招式？", "title_en": "rock-slide"},
    {"q": "污泥炸弹的威力是多少？", "title_en": "sludge-bomb"},
    {"q": "毒击是什么属性的招式？", "title_en": "poison-jab"},
    {"q": "大字爆炎的威力是多少？", "title_en": "fire-blast"},
    {"q": "能量球是什么属性的招式？", "title_en": "energy-ball"},
    {"q": "恶之波动有什么效果？", "title_en": "dark-pulse"},
    {"q": "勇鸟猛攻的威力是多少？", "title_en": "brave-bird"},
    {"q": "拍落有什么效果？", "title_en": "knock-off"},
    {"q": "急速折返的威力是多少？", "title_en": "u-turn"},
    {"q": "近身战有什么效果？", "title_en": "close-combat"},
    {"q": "月亮之力是什么属性的招式？", "title_en": "moonblast"},
    {"q": "水炮的威力是多少？", "title_en": "hydro-pump"},
    # —— 特性扩展（8）——
    {"q": "飘浮有什么效果？", "title_en": "levitate"},
    {"q": "威吓特性的效果是什么？", "title_en": "intimidate"},
    {"q": "自然回复有什么效果？", "title_en": "natural-cure"},
    {"q": "再生力有什么效果？", "title_en": "regenerator"},
    {"q": "粗糙皮肤有什么效果？", "title_en": "rough-skin"},
    {"q": "厚脂肪有什么效果？", "title_en": "thick-fat"},
    {"q": "坚硬脑袋的效果是什么？", "title_en": "rock-head"},
    {"q": "下载特性的效果是什么？", "title_en": "download"},
    # —— 道具扩展（6）——
    {"q": "讲究头带有什么效果？", "title_en": "choice-band"},
    {"q": "讲究眼镜的效果是什么？", "title_en": "choice-specs"},
    {"q": "突击背心有什么效果？", "title_en": "assault-vest"},
    {"q": "凹凸头盔的效果是什么？", "title_en": "rocky-helmet"},
    {"q": "黑色污泥有什么效果？", "title_en": "black-sludge"},
    {"q": "厚底靴有什么效果？", "title_en": "heavy-duty-boots"},
    # —— Meta（10）——
    {"q": "现在 Gen9 OU 环境最热门的宝可梦是谁？", "title_en": "gen9ou"},
    {"q": "当前 UU 环境使用率最高的宝可梦？", "title_en": "gen9uu"},
    {"q": "RU 环境的使用率怎么样？", "title_en": "gen9ru"},
    {"q": "NU 环境什么宝可梦使用率第一？", "title_en": "gen9nu"},
    {"q": "PU 环境使用率最高的宝可梦？", "title_en": "gen9pu"},
    {"q": "Ubers 分级环境怎么样？", "title_en": "gen9ubers"},
    {"q": "第八世代 OU 环境使用率？", "title_en": "gen8ou"},
    {"q": "第八世代 Ubers 环境？", "title_en": "gen8ubers"},
    {"q": "今年八月 OU 使用率前十是谁？", "title_en": "gen9ou"},
    {"q": "Gen9 环境哪些宝可梦使用率最高？", "title_en": "gen9ou"},
]


def resolve_card(title_en: str) -> str | None:
    for name in ["pokemon", "move", "ability", "item", "meta"]:
        with open(os.path.join(CARDS_DIR, f"{name}.jsonl"), encoding="utf-8") as f:
            for line in f:
                card = json.loads(line)
                if card["title_en"].lower() == title_en.lower():
                    return card["card_id"]
    return None


def main() -> int:
    failures = []
    hits_top1 = hits_top3 = hits_top10 = 0
    for q in QUESTIONS:
        expected = resolve_card(q["title_en"])
        if not expected:
            print(f"⚠️ 评测集错误：找不到卡片 {q['title_en']}")
            continue
        ranked = [cid for cid, _ in search(q["q"], top_k=20)]
        if ranked[0] == expected:
            hits_top1 += 1
        if expected in ranked[:3]:
            hits_top3 += 1
        if expected in ranked[:10]:
            hits_top10 += 1
        else:
            failures.append((q["q"], expected, ranked[:5]))

    n = len(QUESTIONS)
    print(f"样本 {n} · top-1 {hits_top1 / n:.0%} · top-3 {hits_top3 / n:.0%} · top-10 {hits_top10 / n:.0%}")
    for q, expected, got in failures:
        print(f"  ❌ {q} -> 期望 {expected}，实际 {got}")
    return 0 if hits_top3 / n >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())
