from datetime import datetime, timezone
from typing import Optional


_TIER_DECAY_MULTIPLIER: dict[int, float] = {
    1: 1.0,
    2: 1.5,
    3: 2.0,
}

_DECAY_PER_WEEK: float = 2.0
_BASE_SCORE: int = 100


def compute_health_score(
    last_contacted_at: Optional[datetime],
    tier: int = 2,
) -> int:
    """Return a health score in [0, 100] for a contact.

    Formula:
        score = 100 - (weeks_since_contact * decay_per_week * tier_multiplier)

    Tier multipliers:
        Tier 1 (VIP):    1.0  → no penalty amplification
        Tier 2 (active): 1.5  → moderate decay
        Tier 3 (dormant):2.0  → fastest decay
    """
    if last_contacted_at is None:
        return 0

    now = datetime.now(timezone.utc)

    # Normalise to UTC-aware datetime if naive
    if last_contacted_at.tzinfo is None:
        last_contacted_at = last_contacted_at.replace(tzinfo=timezone.utc)

    weeks_elapsed = max((now - last_contacted_at).total_seconds() / (7 * 24 * 3600), 0.0)
    multiplier = _TIER_DECAY_MULTIPLIER.get(tier, _TIER_DECAY_MULTIPLIER[2])
    penalty = weeks_elapsed * _DECAY_PER_WEEK * multiplier
    score = _BASE_SCORE - penalty
    return max(0, min(100, round(score)))
