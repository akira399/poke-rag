"""typechart 克制计算单测（纯函数，无网络）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline.typechart import defense_matrix, load_typechart, weakness_text

_HAS_DATA = os.path.exists(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "raw", "showdown", "json", "typechart.json"))


def _chart():
    assert _HAS_DATA, "typechart.json 未生成，先运行 fetch_showdown.mjs"
    return load_typechart()


class TestDefenseMatrix:
    def test_dragonite_weaknesses(self):
        m = defense_matrix(["dragon", "flying"], _chart())
        assert m["ice"] == 4.0      # 龙+飞对冰：2×2
        assert m["dragon"] == 2.0
        assert m["fairy"] == 2.0
        assert m["ground"] == 0.0   # 飞行免疫地面
        assert m["fire"] == 0.5     # 龙抗火、飞抗火

    def test_case_insensitive_keys(self):
        # damageTaken 键首字母大写（'Bug'），函数内部应归一化
        m = defense_matrix(["bug"], _chart())
        assert m["fighting"] == 0.5  # 虫抵抗格斗


class TestWeaknessText:
    def test_dragonite_text(self):
        text = weakness_text(["dragon", "flying"], _chart())
        assert "冰" in text and "免疫" in text and "地面" in text

    def test_pikachu(self):
        text = weakness_text(["electric"], _chart())
        assert "地面" in text

    def test_empty_types(self):
        assert weakness_text([], _chart()) == ""
