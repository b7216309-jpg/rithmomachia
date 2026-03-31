"""Tests for victory detection — progression finding."""

import pytest
from engine.victory import (
    is_arithmetic, is_geometric, is_harmonic,
    find_progressions, check_victory, values_needed_for_progression,
    classify_victory, VictoryType,
)
from engine.models import ProgressionType


class TestArithmetic:
    def test_basic_ap(self):
        assert is_arithmetic((4, 8, 12))

    def test_longer_ap(self):
        assert is_arithmetic((2, 4, 6, 8))

    def test_not_ap(self):
        assert not is_arithmetic((1, 2, 4))

    def test_too_short(self):
        assert not is_arithmetic((1, 2))

    def test_constant_not_ap(self):
        """Same value repeated is not a valid AP (diff=0)."""
        assert not is_arithmetic((5, 5, 5))


class TestGeometric:
    def test_basic_gp(self):
        assert is_geometric((3, 9, 27))

    def test_ratio_2(self):
        assert is_geometric((2, 4, 8))

    def test_longer_gp(self):
        assert is_geometric((2, 6, 18))

    def test_not_gp(self):
        assert not is_geometric((2, 4, 9))

    def test_too_short(self):
        assert not is_geometric((2, 4))

    def test_decreasing_not_gp(self):
        """Only increasing sequences count."""
        assert not is_geometric((27, 9, 3))

    def test_with_zero(self):
        assert not is_geometric((0, 0, 0))


class TestHarmonic:
    def test_basic_hp(self):
        """3, 4, 6: b = 2×3×6/(3+6) = 36/9 = 4 ✓"""
        assert is_harmonic((3, 4, 6))

    def test_another_hp(self):
        """6, 8, 12: b = 2×6×12/(6+12) = 144/18 = 8 ✓"""
        assert is_harmonic((6, 8, 12))

    def test_not_hp(self):
        assert not is_harmonic((3, 5, 6))

    def test_too_short(self):
        assert not is_harmonic((3, 4))

    def test_longer_hp(self):
        """6, 8, 12 is HP. Check 4-term: need each consecutive triple valid."""
        # 6, 8, 12, 24? Check: 8 = 2*6*12/(6+12) = 8 ✓, 12 = 2*8*24/(8+24) = 384/32 = 12 ✓
        assert is_harmonic((6, 8, 12, 24))


class TestFindProgressions:
    def test_finds_arithmetic(self):
        progs = find_progressions([4, 8, 12])
        types = {p.progression_type for p in progs}
        assert ProgressionType.ARITHMETIC in types

    def test_finds_geometric(self):
        progs = find_progressions([3, 9, 27])
        types = {p.progression_type for p in progs}
        assert ProgressionType.GEOMETRIC in types

    def test_finds_harmonic(self):
        progs = find_progressions([3, 4, 6])
        types = {p.progression_type for p in progs}
        assert ProgressionType.HARMONIC in types

    def test_no_progression(self):
        progs = find_progressions([1, 7, 13])
        # 1, 7, 13 is AP with diff 6!
        types = {p.progression_type for p in progs}
        assert ProgressionType.ARITHMETIC in types

    def test_not_enough_captures(self):
        progs = find_progressions([5, 10])
        assert progs == []

    def test_mixed_values_finds_subset(self):
        """Among [2, 4, 6, 9, 27], should find AP(2,4,6) and GP(3,9,27) — but 3 isn't there."""
        progs = find_progressions([2, 4, 6, 9, 27])
        types = {p.progression_type for p in progs}
        assert ProgressionType.ARITHMETIC in types  # 2, 4, 6

    def test_duplicate_values_handled(self):
        """Duplicate values are deduplicated."""
        progs = find_progressions([4, 4, 8, 12])
        types = {p.progression_type for p in progs}
        assert ProgressionType.ARITHMETIC in types


class TestCheckVictory:
    def test_victory_with_ap(self):
        progs = check_victory([4, 8, 12])
        assert len(progs) > 0

    def test_no_victory(self):
        progs = check_victory([1, 5])
        assert len(progs) == 0


class TestValuesNeeded:
    def test_arithmetic_need(self):
        """With 4 and 12 captured, need 8 for AP(4,8,12)."""
        needed = values_needed_for_progression([4, 12], [8, 15, 20])
        assert 8 in needed
        descs = needed[8]
        assert any("arithmetic" in d for d in descs)

    def test_geometric_need(self):
        """With 3 and 27 captured, need 9 for GP(3,9,27)."""
        needed = values_needed_for_progression([3, 27], [9, 15])
        assert 9 in needed
        descs = needed[9]
        assert any("geometric" in d for d in descs)

    def test_only_existing_enemy_values(self):
        """Should only return values that exist among living enemy pieces."""
        needed = values_needed_for_progression([4, 12], [15, 20])
        # 8 would complete AP but isn't among enemies
        assert 8 not in needed


class TestVictoryClassification:
    def test_no_victory(self):
        progs = check_victory([1, 5])
        assert classify_victory(progs) == VictoryType.NONE

    def test_victoria_minor_arithmetic(self):
        """3 captures forming an AP = Victoria Minor."""
        progs = check_victory([4, 8, 12])
        vtype = classify_victory(progs)
        assert vtype == VictoryType.MINOR

    def test_victoria_minor_geometric(self):
        """3 captures forming a GP = Victoria Minor."""
        progs = check_victory([3, 9, 27])
        vtype = classify_victory(progs)
        assert vtype == VictoryType.MINOR

    def test_victoria_minor_harmonic(self):
        """3 captures forming an HP = Victoria Minor."""
        progs = check_victory([3, 4, 6])
        vtype = classify_victory(progs)
        assert vtype == VictoryType.MINOR

    def test_victoria_magna(self):
        """4+ captures with two different progression types = Victoria Magna.

        Values: 2, 4, 6, 8 → AP(2,4,6), AP(4,6,8), AP(2,4,6,8)
        Plus: 2, 4, 8 → GP(2,4,8)
        Two types (arithmetic + geometric) with 4+ values = Magna.
        """
        progs = check_victory([2, 4, 6, 8])
        vtype = classify_victory(progs)
        assert vtype == VictoryType.MAGNA

    def test_victoria_excellentissima(self):
        """All three progression types present = Victoria Excellentissima.

        Need arithmetic + geometric + harmonic from captured values.
        Values: 3, 4, 6, 8, 12
        - AP: 4, 8, 12 (diff=4)
        - HP: 3, 4, 6 (b=2*3*6/(3+6)=4 ✓)
        - GP: 3, 6, 12 (ratio=2)
        All three types → Excellentissima.
        """
        progs = check_victory([3, 4, 6, 8, 12])
        types_found = {p.progression_type for p in progs}
        assert ProgressionType.ARITHMETIC in types_found
        assert ProgressionType.HARMONIC in types_found
        assert ProgressionType.GEOMETRIC in types_found
        vtype = classify_victory(progs)
        assert vtype == VictoryType.EXCELLENTISSIMA
