"""Single slot-selection solver for the cheapest hours sensors.

Every feature is a *rule* on one selection problem, not a processing step:

* ``price_limit``            hard limit, slots beyond it are not selected
                             (per slot; on the mean of the block for a single block)
* ``max_number_of_slots`` + ``flexible_limit``
                             extra slots (on top of ``number_of_slots``) are only
                             allowed while they are within the flexible limit,
                             which is enforced as a hard bound when active
* ``min_seq_slots`` / ``number_of_blocks``
                             every block of consecutive slots has a bounded length
* ``single_block``           the selection is one block (sequential sensor)

Callers translate configuration into a ``SelectionRules`` object and call
``select_slots``. They never coordinate phases themselves.

Two engines sit behind ``select_slots``, because the two sensor types differ in
what a flexible extension *means*:

* several blocks: one dynamic program picks the largest feasible number of slots
  and, for that number, the cheapest combination, all rules at once.
* single block: the cheapest block of ``number_of_slots`` is selected first and is
  then grown at its edges. That anchoring is the documented behaviour of the
  sequential sensor; a joint optimum would silently replace the cheapest block
  by a different, longer one.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

# Prices are floats; treat differences below this as ties (earliest/longest wins).
_EPS = 1e-9
_INF = float("inf")


@dataclass(frozen=True)
class SelectionRules:
    """Declarative constraints for slot selection. Defaults are neutral."""

    number_of_slots: int
    inversed: bool = False
    price_limit: float | None = None
    # Flexible slots: active only when both values are set.
    max_number_of_slots: int | None = None
    flexible_limit: float | None = None
    # Block structure
    min_seq_slots: int = 1
    number_of_blocks: int | None = None  # takes precedence over min_seq_slots
    single_block: bool = False

    @property
    def flex_active(self) -> bool:
        """Return True when flexible slots are enabled."""
        return self.flexible_limit is not None and self.max_number_of_slots is not None


def select_slots(data: list[dict], rules: SelectionRules) -> list[dict]:
    """Select slots from ``data`` under ``rules``.

    ``data`` must be chronological and contiguous (index adjacency equals time
    adjacency) and hold dicts with a ``price`` key. The selection is returned in
    chronological order.
    """
    if not data or rules.number_of_slots <= 0:
        return []
    if rules.single_block:
        indices = _select_single_block(data, rules)
    else:
        indices = _select_multi_block(data, rules)
    return [data[i] for i in indices]


def _past(price: float, limit: float, inversed: bool) -> bool:
    """Return True when ``price`` is on the wrong side of ``limit``."""
    return price < limit if inversed else price > limit


# --------------------------------------------------------------------------- #
# Several blocks
# --------------------------------------------------------------------------- #
def _greedy(
    data: list[dict], eligible: list[bool], target: int, mult: int
) -> list[int]:
    """Return the ``target`` cheapest eligible slots, earliest first on ties.

    ``target`` never exceeds the number of slots within the flexible limit plus the
    budget, and slots within the limit are strictly cheaper than slots beyond it.
    The slots beyond the limit that are picked therefore stay within the budget.
    """
    order = sorted(
        (i for i in range(len(data)) if eligible[i]),
        key=lambda i: (data[i]["price"] * mult, i),
    )
    return sorted(order[:target])


def _select_multi_block(data: list[dict], rules: SelectionRules) -> list[int]:
    n = len(data)
    mult = -1 if rules.inversed else 1

    # lists all slots, slot is False when above price_limit. Otherwise it's true (or inversed)
    if rules.price_limit is None:
        eligible = [True] * n
    else:
        eligible = [
            not _past(item["price"], rules.price_limit, rules.inversed) for item in data
        ]

    # Only relevant is flexbile slots are active. If so, returns slots beyond base, within flexible price limit.
    if rules.flex_active:
        eligible = [
            ok and not _past(item["price"], rules.flexible_limit, rules.inversed)
            for ok, item in zip(eligible, data)
        ]

    base = rules.number_of_slots
    # Total number of slots within eligible and flexible_limit (beyond)
    available = sum(eligible)
    # Max number of slots eg base or flex
    ceiling = max(base, rules.max_number_of_slots) if rules.flex_active else base
    # Highest possible slots with restrictions. Returns if 0
    target = min(ceiling, available)
    if target <= 0:
        return []

    blocks = (
        rules.number_of_blocks
        if rules.number_of_blocks and rules.number_of_blocks > 0
        else None
    )

    # No block constraints: plain greedy.
    if blocks is None and rules.min_seq_slots <= 1:
        return _greedy(data, eligible, target, mult)

    # Creates three tables for quick math:
    # run[i]: How many continous slots are eligible? Determines how long a block can be
    # prefix[i]: Cumulatve price of blocks combined in order to select the cheapest overall
    # bprefix[i]: Beyond prefix, to determine how many expesive slots are in a block.
    run = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        run[i] = run[i + 1] + 1 if eligible[i] else 0
    prefix = [0.0]
    for item in data:
        prefix.append(prefix[-1] + item["price"] * mult)

    # DP solver.
    def solve(k_max: int, lo: int, hi: int, exact: bool) -> list[int] | None:
        """Cheapest selection of up to ``k_max`` slots (exactly, if ``exact``).

        dp[i][k]: minimal cost of k slots from i..n-1, given slot i-1 is not
        selected. A mandatory gap after each block keeps blocks from merging, so
        length bounds hold. On ties the earlier and longer block wins.
        """
        dp = [[_INF] * (k_max + 1) for _ in range(n + 1)]
        choice = [[0] * (k_max + 1) for _ in range(n + 1)]
        dp[n][0] = 0.0

        for i in range(n - 1, -1, -1):
            for k in range(k_max + 1):
                best, best_choice = _INF, 0
                for length in range(min(hi, k, run[i]), lo - 1, -1):
                    rest = dp[min(i + length + 1, n)][k - length]
                    if rest == _INF:
                        continue
                    cost = prefix[i + length] - prefix[i] + rest
                    if cost < best - _EPS:
                        best, best_choice = cost, length
                skip = dp[i + 1][k]
                if skip < best - _EPS:
                    best, best_choice = skip, 0
                dp[i][k] = best
                choice[i][k] = best_choice

        counts = [k_max] if exact else range(k_max, 0, -1)
        best_k = next((k for k in counts if k > 0 and dp[0][k] < _INF), 0)
        if best_k == 0:
            return None

        selected: list[int] = []
        i, k = 0, best_k
        while i < n and k > 0:
            length = choice[i][k]
            if length == 0:
                i += 1
            else:
                selected.extend(range(i, i + length))
                k -= length
                i = min(i + length + 1, n)
        return selected

    selected: list[int] | None = None
    if blocks is not None:
        # Block bounds follow from the slot count, so the largest feasible count
        # is searched from the top: k slots divided over at most `blocks` blocks.
        for k in range(target, 0, -1):
            b = min(blocks, k)
            selected = solve(k, k // b, math.ceil(k / b), exact=True)
            if selected is not None:
                break
    else:
        selected = solve(target, max(rules.min_seq_slots, 1), n, exact=False)

    if selected is None:
        # Block rules cannot be met: fall back to the cheapest allowed slots.
        return _greedy(data, eligible, target, mult)
    return selected


# --------------------------------------------------------------------------- #
# Single block
# --------------------------------------------------------------------------- #
def _select_single_block(data: list[dict], rules: SelectionRules) -> list[int]:
    n = len(data)
    base = rules.number_of_slots
    if base > n:
        return []
    prices = [item["price"] for item in data]

    # Cheapest (or most expensive) block of `base` slots; the earliest wins ties.
    best_start = -1
    best_total = 0.0
    for start in range(n - base + 1):
        total = sum(prices[start : start + base])
        if best_start == -1 or (
            total > best_total if rules.inversed else total < best_total
        ):
            best_start, best_total = start, total

    # price_limit judges the base block as a whole, by its mean.
    if rules.price_limit is not None and _past(
        best_total / base, rules.price_limit, rules.inversed
    ):
        return []

    start, end = best_start, best_start + base
    if rules.flex_active:
        extra = max(0, rules.max_number_of_slots - base)
        start, end = _extend_block(
            prices, start, end, extra, rules.flexible_limit, rules.inversed
        )
    return list(range(start, end))


def _extend_block(
    prices: list[float],
    start: int,
    end: int,
    max_extra: int,
    limit: float,
    inversed: bool,
) -> tuple[int, int]:
    """Grow [start, end) with the best neighbouring slot while it is within limit.

    On equal prices the earlier (left) slot is preferred.
    """
    mult = -1 if inversed else 1
    for _ in range(max_extra):
        candidates = []
        if start > 0:
            candidates.append((prices[start - 1] * mult, 0))
        if end < len(prices):
            candidates.append((prices[end] * mult, 1))
        if not candidates:
            break
        score, side = min(candidates)
        if score > limit * mult:
            break  # the best neighbour is beyond the limit, so is the other one
        if side == 0:
            start -= 1
        else:
            end += 1
    return start, end
