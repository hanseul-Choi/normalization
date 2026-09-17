"""CJK (Chinese, Japanese, Korean) specific ideograph markers for deterministic script and language discrimination."""

from __future__ import annotations

# Japanese Kokuji (Japanese-coined kanji) and prominent Shinjitai characters
# that appear almost exclusively in Japanese texts.
JAPANESE_SPECIFIC_HAN: frozenset[str] = frozenset([
    "峠", "畠", "辻", "込", "枠", "畑", "躾", "鱈", "笹", "榊",
    "栃", "鋲", "働", "蛯", "鰯", "鯎", "鞄", "匂", "籾", "凪",
    "駅", "円", "桜", "鉄", "竜", "図", "売", "払", "対", "庁",
])

# Simplified Chinese characters that do not appear in standard Japanese Joyo/Jinmeiyo Kanji
# and are distinct from Traditional Chinese.
SIMPLIFIED_CHINESE_SPECIFIC_HAN: frozenset[str] = frozenset([
    "门", "语", "发", "经", "动", "们", "这", "对", "关", "问",
    "题", "济", "学", "习", "网", "站", "给", "让", "说", "话",
    "电", "脑", "车", "银", "行", "现", "在", "时", "间", "机",
    "场", "报", "告", "统", "计", "资", "料", "设", "备", "计",
    "算", "软", "件", "硬", "件", "邮", "箱", "账", "户", "密",
    "码", "验", "证", "浏", "览", "器", "服", "务", "器", "链",
    "接", "下", "载", "创", "建", "更", "新", "删", "除", "查",
    "询", "确", "认", "取", "消", "成", "功", "失", "败", "提",
])

# Traditional Chinese characters distinctive from Simplified and Japanese
TRADITIONAL_CHINESE_SPECIFIC_HAN: frozenset[str] = frozenset([
    "門", "語", "發", "經", "動", "們", "這", "對", "關", "問",
    "題", "濟", "學", "習", "網", "站", "給", "讓", "說", "話",
    "電", "腦", "車", "銀", "行", "現", "在", "時", "間", "機",
    "場", "報", "告", "統", "計", "資", "料", "設", "備", "計",
    "算", "軟", "體", "硬", "體", "郵", "箱", "帳", "戶", "密",
    "碼", "驗", "證", "瀏", "覽", "器", "服", "務", "器", "鏈",
    "結", "下", "載", "創", "建", "更", "新", "刪", "除", "查",
    "詢", "確", "認", "取", "消", "成", "功", "失", "敗", "提",
])
