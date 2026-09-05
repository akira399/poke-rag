/**
 * M0 · 下载 Pokémon Showdown data/*.ts 并转译为 JSON（data/raw/showdown/）
 *
 * 数据文件是 TypeScript 常量对象（export const X = {...}），用 esbuild
 * 做类型剥离得到 CJS，再 require 导出 JSON。原始 .ts 保留（raw 层只读），
 * 转换脚本可重复执行。
 *
 * 运行：node scripts/fetch_showdown.mjs
 */
import { createRequire } from "module";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import esbuild from "esbuild";

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const SRC_DIR = path.join(ROOT, "data", "raw", "showdown", "src");
const OUT_DIR = path.join(ROOT, "data", "raw", "showdown", "json");

/**
 * 本机 CA 证书链被代理中断，Node 内建 fetch 校验失败（UNABLE_TO_VERIFY_
 * LEAF_SIGNATURE），下载统一走系统 curl -k。生产环境应恢复真实验证。
 */
const CURL_INSECURE = ["curl", "-skL"];

async function download(url, outPath) {
  if (fs.existsSync(outPath)) return "skip";
  const { execFileSync } = await import("child_process");
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  const buf = execFileSync(CURL_INSECURE[0], [...CURL_INSECURE.slice(1), url], {
    maxBuffer: 64 * 1024 * 1024,
  });
  fs.writeFileSync(outPath, buf, "utf-8");
  return "ok";
}

const BASE = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data";

// data/ 目录核心数据文件（对战规则与图鉴主数据）
const DATA_FILES = [
  "pokedex",       // 图鉴：种族值/属性/特性/进化（1518 条含形态）
  "moves",         // 招式：威力/命中/PP/效果（1475+ 条）
  "abilities",     // 特性：效果机制字段
  "items",         // 道具：效果机制字段（对战向）
  "learnsets",     // 每只宝可梦可学习招式表
  "natures",       // 性格：加成表
  "typechart",     // 属性克制表（规则引擎数据源）
  "conditions",    // 天气/场地/异常状态
  "formats-data",  // 分级（OU/UU/UBER…）
  "aliases",       // 别名表（并入 M1 别名映射）
  "tags",
];

// data/text/*.ts：人类可读的英文效果描述（shortDesc），缺失效果文本的兜底来源
const TEXT_SRC = ["items", "moves", "abilities"];

function transpile(tsCode) {
  return esbuild.transformSync(tsCode, {
    loader: "ts",
    format: "cjs",
    logLevel: "silent",
  }).code;
}

function exportToJson(tsFile, jsonFile) {
  const jsCode = transpile(fs.readFileSync(tsFile, "utf-8"));
  const tmp = tsFile + ".tmp.cjs";
  fs.writeFileSync(tmp, jsCode, "utf-8");
  const mod = require(tmp);
  fs.rmSync(tmp);
  const entries = Object.entries(mod).filter(([k]) => !k.startsWith("__"));
  fs.mkdirSync(path.dirname(jsonFile), { recursive: true });
  fs.writeFileSync(jsonFile, JSON.stringify(Object.fromEntries(entries), null, 2), "utf-8");
  return entries.map(([k]) => k).join(", ");
}

async function main() {
  for (const name of DATA_FILES) {
    const tsPath = path.join(SRC_DIR, `${name}.ts`);
    await download(`${BASE}/${name}.ts`, tsPath);
    const exported = exportToJson(tsPath, path.join(OUT_DIR, `${name}.json`));
    console.log(`[data] ${name}.ts -> ${name}.json  (导出: ${exported})`);
  }
  for (const name of TEXT_SRC) {
    const tsPath = path.join(SRC_DIR, "text", `${name}.ts`);
    await download(`${BASE}/text/${name}.ts`, tsPath);
    const exported = exportToJson(tsPath, path.join(OUT_DIR, `text-${name}.json`));
    console.log(`[text] text/${name}.ts -> text-${name}.json  (导出: ${exported})`);
  }
  console.log("完成。输出目录:", OUT_DIR);
}

main().catch((err) => {
  console.error("失败:", err.message);
  process.exit(1);
});
