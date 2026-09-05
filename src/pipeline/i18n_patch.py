"""汉化补丁表：PokeAPI 官方简体中文名缺失的实体，采用通行译名/意译。

来源与原则：
- ability 63 条：Pokémon XD/同人特性，官方无中文，采用通行意译；
- move 18 条：暗影招式（Pokémon XD），官方无中文，采用通行意译；
- item：极巨结晶系列（收藏向）规则化命名；少量常用道具补通行译名。
"""

ABILITY_PATCH = {
    "mountaineer": "登山者", "wave-rider": "弄潮儿", "skater": "滑板手",
    "thrust": "突刺", "perception": "敏锐", "parry": "招架", "instinct": "直觉",
    "dodge": "闪避", "jagged-edge": "锯齿刃", "frostbite": "冻伤",
    "tenacity": "坚韧", "pride": "自尊", "deep-sleep": "深眠",
    "power-nap": "小憩", "spirit": "灵魂", "warm-blanket": "暖毯",
    "gulp": "吞咽", "herbivore": "食草", "sandpit": "沙坑",
    "hot-blooded": "热血", "medic": "医者", "life-force": "生命力",
    "lunchbox": "便当盒", "nurse": "护士", "melee": "近战", "sponge": "海绵",
    "bodyguard": "保镖", "hero": "英雄", "last-bastion": "最后堡垒",
    "stealth": "潜行", "vanguard": "先锋", "nomad": "游牧", "sequence": "序列",
    "grass-cloak": "草斗篷", "celebrate": "庆祝", "lullaby": "摇篮曲",
    "calming": "镇定", "daze": "眩晕", "frighten": "惊吓",
    "interference": "干扰", "mood-maker": "气氛制造者", "confidence": "自信",
    "fortune": "幸运", "bonanza": "大丰收", "explode": "爆炸",
    "omnipotent": "全能", "share": "分享", "black-hole": "黑洞",
    "shadow-dash": "影袭", "sprint": "疾跑", "disgust": "厌恶",
    "high-rise": "高楼", "climber": "攀爬者", "flame-boost": "烈焰强化",
    "aqua-boost": "水波强化", "run-up": "助跑", "conqueror": "征服者",
    "shackle": "枷锁", "decoy": "诱饵", "shield": "护盾", "eelevate": "升空",
    "fire-mane": "火鬃", "aura-guard": "气场守护",
}

MOVE_PATCH = {
    "shadow-rush": "暗影突袭", "shadow-blast": "暗影爆发",
    "shadow-blitz": "暗影强袭", "shadow-bolt": "暗影电击",
    "shadow-break": "暗影粉碎", "shadow-chill": "暗影寒气",
    "shadow-end": "暗影终结", "shadow-fire": "暗影火焰",
    "shadow-rave": "暗影狂乱", "shadow-storm": "暗影风暴",
    "shadow-wave": "暗影波动", "shadow-down": "暗影坠落",
    "shadow-half": "暗影减半", "shadow-hold": "暗影禁锢",
    "shadow-mist": "暗影迷雾", "shadow-panic": "暗影恐慌",
    "shadow-shed": "暗影蜕皮", "shadow-sky": "暗影天空",
}

ITEM_PATCH = {
    "raichunite": "雷丘石", "grass-mail": "草地邮件", "flame-mail": "火焰邮件",
    "bubble-mail": "气泡邮件", "bloom-mail": "鲜花邮件", "tunnel-mail": "隧道邮件",
    "steel-mail": "钢铁邮件", "heart-mail": "爱心邮件", "snow-mail": "雪花邮件",
}


def patch_title(kind: str, en_slug: str) -> str:
    """按类型查补丁表；极巨结晶按规则化命名。无补丁返回空串。"""
    if kind == "ability":
        return ABILITY_PATCH.get(en_slug, "")
    if kind == "move":
        return MOVE_PATCH.get(en_slug, "")
    if kind == "item":
        if en_slug.startswith("dynamax-crystal-"):
            return "极巨结晶·" + en_slug[len("dynamax-crystal-"):].upper()
        return ITEM_PATCH.get(en_slug, "")
    return ""
