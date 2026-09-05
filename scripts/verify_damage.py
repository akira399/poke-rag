"""M5 · 伤害引擎对拍：本引擎 vs 官方 @smogon/calc（100 组随机用例）。

两边输入同源（Showdown pokedex/moves 数据），IV=31/EV=0/无特性修正，
容差 ±1（舍入链一致则应为 0）。对拍失败即引擎公式有误。
"""
import json
import random
import subprocess
import sys

sys.path.insert(0, ".")

from src.rules.damage import DamageInput, calc_damage  # noqa: E402

POKEDEX = json.load(open("data/raw/showdown/json/pokedex.json", encoding="utf-8"))["Pokedex"]
MOVES = json.load(open("data/raw/showdown/json/moves.json", encoding="utf-8"))["Moves"]
LEARNSETS = json.load(open("data/raw/showdown/json/learnsets.json", encoding="utf-8"))["Learnsets"]

POOL = {
    "attacker": ["dragonite", "gengar", "pikachu", "gyarados", "snorlax", "garchomp",
                 "togekiss", "ferrothorn", "heatran", "landorustherian"],
    "defender": ["blissey", "skarmory", "toxapex", "corviknight", "dragonite", "garchomp",
                 "gastrodon", "hydreigon", "amoonguss", "tyranitar"],
    "moves": ["earthquake", "thunderbolt", "ice-beam", "flamethrower", "surf", "dragon-claw",
              "shadow-ball", "u-turn", "knock-off", "fire-blast", "hurricane", "close-combat",
              "moonblast", "energy-ball", "dark-pulse", "brave-bird", "hydro-pump", "stone-edge"],
}


def gen_stat(base: int, level: int, iv: int = 31, ev: int = 0, hp: bool = False) -> int:
    if hp:
        return (2 * base + iv + ev // 4) * level // 100 + level + 10
    return (2 * base + iv + ev // 4) * level // 100 + 5


def make_cases(seed: int = 42, n: int = 100) -> list[dict]:
    rng = random.Random(seed)
    cases = []
    while len(cases) < n:
        an = rng.choice(POOL["attacker"])
        dn = rng.choice(POOL["defender"])
        # 招式必须合法：在攻击方学习表内且带威力（@smogon/calc 对非法组合返回 damage=0）
        learnset = LEARNSETS.get(an, {}).get("learnset", {})
        avail = [m for m in POOL["moves"]
                 if m.replace("-", "") in learnset and MOVES.get(m, {}).get("basePower")]
        if not avail:
            continue
        mn = rng.choice(avail)
        cases.append({"attacker": an, "move": mn, "defender": dn,
                      "level": rng.choice([50, 100])})
    return cases


def engine_calc(cases: list[dict]) -> list[dict]:
    results = []
    for c in cases:
        a = POKEDEX[c["attacker"]]
        d = POKEDEX[c["defender"]]
        mv = MOVES[c["move"]]
        style = "physical" if str(mv.get("category", "")).lower() == "physical" else "special"
        atk_base = a["baseStats"]["atk" if style == "physical" else "spa"]
        def_base = d["baseStats"]["def" if style == "physical" else "spd"]
        move_type = str(mv.get("type", "")).lower()
        atk_types = [t.lower() for t in a["types"]]
        def_types = [t.lower() for t in d["types"]]
        ci = DamageInput(
            level=c["level"],
            power=mv.get("basePower") or 0,
            atk=gen_stat(atk_base, c["level"]),
            defense=gen_stat(def_base, c["level"]),
            stab=move_type in atk_types,
            move_type=move_type,
            defender_types=def_types,
        )
        lo, hi = calc_damage(ci)
        results.append({"case": c, "mine": [lo, hi]})
    return results


def main() -> int:
    cases = make_cases()
    engine = engine_calc(cases)

    with open("data/tmp_cases.json", "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False)
    proc = subprocess.run(
        ["node", "scripts/verify_damage.cjs"], capture_output=True, text=True, cwd="."
    )
    if proc.returncode != 0:
        print("node 对拍失败:", proc.stderr[-500:])
        return 1
    official = json.loads(proc.stdout)

    passed = 0
    diffs = []
    valid = 0
    for e, o in zip(engine, official):
        if o["damage"] is None:
            continue  # 官方判定 Gen9 非法组合，排除
        valid += 1
        d_lo = abs(e["mine"][0] - o["damage"][0])
        d_hi = abs(e["mine"][1] - o["damage"][1])
        if d_lo <= 1 and d_hi <= 1:
            passed += 1
        else:
            diffs.append((e["case"], e["mine"], o["damage"], d_lo, d_hi))
    print(f"对拍 {len(engine)} 例 · 有效 {valid}（其余为 Gen9 非法组合，按官方判定排除）· "
          f"通过 {passed} · 未过 {len(diffs)}")
    for c, mine, off, d_lo, d_hi in diffs[:5]:
        print(f"  {c['attacker']} {c['move']} vs {c['defender']} L{c['level']}: "
              f"mine {mine} vs official {off} (Δ{max(d_lo,d_hi)})")
    return 0 if passed == valid else 1


if __name__ == "__main__":
    sys.exit(main())
