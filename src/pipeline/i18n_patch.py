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
    "raichunite": "雷丘进化石",
    # 传说 Z-A 新增 Mega 石（PokeAPI 尚无中文；命名规则：<宝可梦中文名>进化石，
    # 中文名取自本项目 pokemon.jsonl 的官方 zh 名，逐一前缀匹配核对）
    "clefablite": "皮可西进化石", "victreebelite": "大食花进化石",
    "starminite": "宝石海星进化石", "dragoninite": "快龙进化石",
    "meganiumite": "大竺葵进化石", "feraligite": "大力鳄进化石",
    "skarmorite": "盔甲鸟进化石", "froslassite": "雪妖女进化石",
    "heatranite": "席多蓝恩进化石", "darkranite": "达克莱伊进化石",
    "emboarite": "炎武王进化石", "excadrite": "龙头地鼠进化石",
    "scolipite": "蜈蚣王进化石", "scraftinite": "头巾混混进化石",
    "eelektrossite": "麻麻鳗鱼王进化石", "chandelurite": "水晶灯火灵进化石",
    "chesnaughtite": "布里卡隆进化石", "delphoxite": "妖火红狐进化石",
    "greninjite": "甲贺忍蛙进化石", "pyroarite": "火炎狮进化石",
    "floettite": "花叶蒂进化石", "malamarite": "乌贼王进化石",
    "barbaracite": "龟足巨铠进化石", "dragalgite": "毒藻龙进化石",
    "hawluchanite": "摔角鹰人进化石", "zygardite": "基格尔德进化石",
    "drampanite": "老翁龙进化石", "zeraorite": "捷拉奥拉进化石",
    "falinksite": "列阵兵进化石", "chimechite": "风铃铃进化石",
    "staraptite": "姆克鹰进化石", "golurkite": "泥偶巨人进化石",
    "meowsticite": "超能妙喵进化石", "crabominite": "好胜毛蟹进化石",
    "golisopite": "具甲武者进化石", "magearnite": "玛机雅娜进化石",
    "scovillainite": "狠辣椒进化石", "baxcalibrite": "戟脊龙进化石",
    "tatsugirinite": "米立龙进化石", "glimmoranite": "晶光花进化石",
    "grass-mail": "草地邮件", "flame-mail": "火焰邮件",
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
