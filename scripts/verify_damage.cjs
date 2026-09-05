/**
 * M5 · 官方伤害计算器（@smogon/calc v3+）对拍侧（CJS）。
 * 读取 data/tmp_cases.json，输出 [{case, damage:[min,max]}]。
 * 新版 API：构造函数第一参数为世代（9）。
 */
const { calculate, Pokemon, Move, Field } = require("@smogon/calc");
const fs = require("fs");

const GEN = 9;
const cases = JSON.parse(fs.readFileSync("data/tmp_cases.json", "utf-8"));
const out = cases.map((c) => {
  const attacker = new Pokemon(GEN, c.attacker, { level: c.level });
  const defender = new Pokemon(GEN, c.defender, { level: c.level });
  const move = new Move(GEN, c.move);
  const res = calculate(GEN, attacker, defender, move, new Field());
  // 官方判定非法组合（全世代学习表有、Gen9 未启用）时 damage 为非数组（0），标记 invalid
  return {
    case: c,
    damage: Array.isArray(res.damage)
      ? [Math.min.apply(null, res.damage), Math.max.apply(null, res.damage)]
      : null,
  };
});
console.log(JSON.stringify(out));
