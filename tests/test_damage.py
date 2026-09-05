"""M5 伤害引擎单测：与官方 (gen9) 公式逐项对齐的关键函数。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rules.damage import (
    DamageInput,
    calc_damage,
    damage_rolls,
    gen_stat,
    get_base_damage,
    ko_probability,
    poke_round,
    type_effectiveness,
)


class TestGenStat:
    def test_level50_formula(self):
        # (2*130+31)*50//100+5 = 150（heatran spa）
        assert gen_stat(130, 50) == 150

    def test_hp_formula(self):
        # (2*98+31)*50//100+50+10 = 173（corviknight hp L50）
        assert gen_stat(98, 50, hp=True) == 173


class TestDamageRolls:
    def test_sixteen_rolls(self):
        rolls = damage_rolls(DamageInput(
            level=50, power=90, atk=150, defense=105,
            move_type="fire", defender_types=["steel", "flying"],
        ))
        assert len(rolls) == 16
        assert rolls[0] < rolls[-1]  # 85% 档 < 100% 档

    def test_ko_probability(self):
        assert ko_probability([50, 60, 70], defender_hp=65) == 1 / 3
        assert ko_probability([50, 60], defender_hp=0) == 1.0


class TestPokeRound:
    def test_half_goes_down(self):
        # 官方规则：小数恰好 0.5 时向下取整（1.5 -> 1）
        assert poke_round(1.5) == 1

    def test_over_half_goes_up(self):
        assert poke_round(1.51) == 2

    def test_integer(self):
        assert poke_round(3.0) == 3


class TestBaseDamage:
    def test_heatran_flamethrower_l50(self):
        # 官方复算：floor(floor(2*50/5+2)*90)*150/105/50+2
        #   = floor(22*90)*150/105/50+2 = 1980*150/105/50+2 = 56+2 = 58
        assert get_base_damage(50, 90, 150, 105) == 58

    def test_level_100(self):
        # floor(42*90)*150/105/50+2 = 108+2 = 110
        assert get_base_damage(100, 90, 150, 105) == 110


class TestCalcDamage:
    def test_zero_effectiveness(self):
        # 地面招式打飞行系（免疫）：0 伤害
        lo, hi = calc_damage(DamageInput(
            power=100, atk=100, defense=100,
            move_type="ground", defender_types=["flying"],
        ), chart={})
        assert (lo, hi) == (0, 0)

    def test_dragonite_weak_to_ice(self):
        # 快龙被冰系招式打：2×2=4 倍（龙+飞），伤害应显著大于普通招式
        lo, hi = calc_damage(DamageInput(
            level=50, power=80, atk=120, defense=100,
            move_type="ice", defender_types=["dragon", "flying"],
        ))
        lo2, hi2 = calc_damage(DamageInput(
            level=50, power=80, atk=120, defense=100,
            move_type="water", defender_types=["dragon", "flying"],
        ))
        assert hi > hi2 * 2  # 4 倍 vs 1 倍（非免疫）

    def test_effectiveness(self):
        # 倍率断言以真实克制表为准，见 test_typechart.py
        assert type_effectiveness("ground", ["flying"], chart={}) == 1.0
