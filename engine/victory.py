"""Victory detection for Rithmomachia.

Checks captured piece values for arithmetic, geometric, and harmonic progressions.

Victory types (in order of prestige):
- Victoria Minor (3 pieces): Any single progression (arithmetic, geometric, or harmonic)
- Victoria Magna (4 pieces): Two different types of progression among 4 captures
- Victoria Excellentissima (4+ pieces): All three progression types present
"""

from __future__ import annotations

from itertools import combinations
from math import gcd

from engine.models import Progression, ProgressionType


def is_arithmetic(values: tuple[int, ...]) -> bool:
    """Check if sorted values form an arithmetic progression (constant difference)."""
    if len(values) < 3:
        return False
    diff = values[1] - values[0]
    if diff == 0:
        return False
    return all(values[i] - values[i - 1] == diff for i in range(2, len(values)))


def is_geometric(values: tuple[int, ...]) -> bool:
    """Check if sorted values form a geometric progression (constant ratio).

    Only considers integer ratios > 1 to avoid degenerate cases.
    """
    if len(values) < 3:
        return False
    if any(v == 0 for v in values):
        return False
    # Check if ratio is constant — use fraction comparison to avoid float issues
    # a/b = c/d iff a*d = b*c
    for i in range(2, len(values)):
        if values[i] * values[i - 2] != values[i - 1] * values[i - 1]:
            return False
    # Ensure ratio > 1 (strictly increasing)
    if values[1] <= values[0]:
        return False
    return True


def is_harmonic(values: tuple[int, ...]) -> bool:
    """Check if sorted values form a harmonic progression.

    In a harmonic progression, each middle term b satisfies:
    b = 2ac / (a + c) where a is the preceding term and c is the following term.
    """
    if len(values) < 3:
        return False
    if any(v == 0 for v in values):
        return False

    for i in range(1, len(values) - 1):
        a, b, c = values[i - 1], values[i], values[i + 1]
        # b = 2ac / (a + c)  →  b * (a + c) = 2ac
        if b * (a + c) != 2 * a * c:
            return False

    # Ensure strictly increasing
    if not all(values[i] > values[i - 1] for i in range(1, len(values))):
        return False

    return True


def find_progressions(captured_values: list[int]) -> list[Progression]:
    """Find all valid progressions (length 3+) among captured values.

    Checks all combinations of 3 or more captured values (sorted) for
    arithmetic, geometric, and harmonic progressions.
    Returns all found progressions.
    """
    if len(captured_values) < 3:
        return []

    progressions: list[Progression] = []
    unique_sorted = sorted(set(captured_values))

    # Check combinations of size 3 up to all values
    for size in range(3, len(unique_sorted) + 1):
        for combo in combinations(unique_sorted, size):
            vals = tuple(combo)  # Already sorted since unique_sorted is sorted

            if is_arithmetic(vals):
                progressions.append(Progression(
                    progression_type=ProgressionType.ARITHMETIC,
                    values=vals,
                ))
            if is_geometric(vals):
                progressions.append(Progression(
                    progression_type=ProgressionType.GEOMETRIC,
                    values=vals,
                ))
            if is_harmonic(vals):
                progressions.append(Progression(
                    progression_type=ProgressionType.HARMONIC,
                    values=vals,
                ))

    return progressions


class VictoryType:
    """Victory classification."""
    NONE = "none"
    MINOR = "victoria_minor"         # 3+ pieces, one progression type
    MAGNA = "victoria_magna"         # 4+ pieces, two different progression types
    EXCELLENTISSIMA = "victoria_excellentissima"  # 4+ pieces, all three types


def classify_victory(progressions: list[Progression]) -> str:
    """Classify the victory level from found progressions."""
    if not progressions:
        return VictoryType.NONE

    # Collect unique progression types found
    types_found = {p.progression_type for p in progressions}

    if len(types_found) >= 3:
        return VictoryType.EXCELLENTISSIMA
    elif len(types_found) >= 2:
        # Need at least 4 captured values total for Magna
        all_values = set()
        for p in progressions:
            all_values.update(p.values)
        if len(all_values) >= 4:
            return VictoryType.MAGNA
        return VictoryType.MINOR
    else:
        return VictoryType.MINOR


def check_victory(captured_values: list[int]) -> list[Progression]:
    """Check if captured values contain any winning progression.

    Returns the list of winning progressions found (empty = no victory).
    Use classify_victory() on the result to determine Minor/Magna/Excellentissima.
    """
    return find_progressions(captured_values)


def values_needed_for_progression(captured_values: list[int],
                                  all_enemy_values: list[int]) -> dict[int, list[str]]:
    """Given current captures, find which enemy values would complete a progression.

    Returns a dict mapping enemy value → list of progression descriptions.
    Only returns values that actually exist among living enemy pieces.
    """
    result: dict[int, list[str]] = {}
    captured_set = set(captured_values)
    enemy_set = set(all_enemy_values)

    # For each pair of captured values, check what third value would
    # form a length-3 progression
    unique_caps = sorted(captured_set)

    for a, c in combinations(unique_caps, 2):
        # Arithmetic: need b where a, b, c is AP — b = (a+c)/2
        # Also: need x where x, a, c or a, c, x is AP
        _check_arithmetic_needs(a, c, captured_set, enemy_set, result)

        # Geometric: need b where a, b, c is GP — b² = ac
        _check_geometric_needs(a, c, captured_set, enemy_set, result)

        # Harmonic: need b where a, b, c is HP — b = 2ac/(a+c)
        _check_harmonic_needs(a, c, captured_set, enemy_set, result)

    return result


def _check_arithmetic_needs(a: int, c: int, captured: set[int],
                            enemies: set[int], result: dict[int, list[str]]) -> None:
    """Find values that would complete an arithmetic progression with a and c."""
    # Middle: b = (a+c)/2
    if (a + c) % 2 == 0:
        b = (a + c) // 2
        if b not in captured and b in enemies and b != a and b != c:
            result.setdefault(b, []).append(f"arithmetic({a},{b},{c})")

    # Extend before: x, a, c where diff = c - a → x = 2a - c
    diff = c - a
    x = a - diff
    if x > 0 and x not in captured and x in enemies:
        result.setdefault(x, []).append(f"arithmetic({x},{a},{c})")

    # Extend after: a, c, x where diff = c - a → x = 2c - a
    x = c + diff
    if x not in captured and x in enemies:
        result.setdefault(x, []).append(f"arithmetic({a},{c},{x})")


def _check_geometric_needs(a: int, c: int, captured: set[int],
                           enemies: set[int], result: dict[int, list[str]]) -> None:
    """Find values that would complete a geometric progression with a and c."""
    # Middle: b² = ac → b = sqrt(ac)
    product = a * c
    b = _isqrt(product)
    if b is not None and b not in captured and b in enemies and a < b < c:
        result.setdefault(b, []).append(f"geometric({a},{b},{c})")

    # Extend before: x, a, c where ratio = c/a → x = a²/c
    if c != 0 and (a * a) % c == 0:
        x = (a * a) // c
        if x > 0 and x != a and x not in captured and x in enemies:
            result.setdefault(x, []).append(f"geometric({x},{a},{c})")

    # Extend after: a, c, x where ratio = c/a → x = c²/a
    if a != 0 and (c * c) % a == 0:
        x = (c * c) // a
        if x != c and x not in captured and x in enemies:
            result.setdefault(x, []).append(f"geometric({a},{c},{x})")


def _check_harmonic_needs(a: int, c: int, captured: set[int],
                          enemies: set[int], result: dict[int, list[str]]) -> None:
    """Find values that would complete a harmonic progression with a and c."""
    # Middle: b = 2ac/(a+c)
    numerator = 2 * a * c
    denominator = a + c
    if denominator != 0 and numerator % denominator == 0:
        b = numerator // denominator
        if a < b < c and b not in captured and b in enemies:
            result.setdefault(b, []).append(f"harmonic({a},{b},{c})")


def _isqrt(n: int) -> int | None:
    """Integer square root. Returns the root if n is a perfect square, else None."""
    if n < 0:
        return None
    if n == 0:
        return 0
    x = int(n ** 0.5)
    # Check x-1, x, x+1 to handle floating point imprecision
    for candidate in (x - 1, x, x + 1):
        if candidate >= 0 and candidate * candidate == n:
            return candidate
    return None
