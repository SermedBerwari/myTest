from datetime import datetime, timezone
import pandas as pd
import pytest
from scripts.decision.intelligence_signals import normalize_signals

DEADLINE=datetime(2026,8,18,12,tzinfo=timezone.utc)

def frame(rows):
    return pd.DataFrame(rows,columns=["player_id","status","signal_timestamp","source"])

def test_priority_and_contradiction_resolution():
    signals=frame([(1,"available","2026-08-18T09:00:00Z","club"),(1,"injury","2026-08-18T10:00:00Z","news"),(2,"suspension","2026-08-18T08:00:00Z","league")])
    out=normalize_signals(signals,DEADLINE,max_age_hours=72)
    p1=out.set_index("player_id").loc[1]
    assert p1["availability"]=="injured"
    assert bool(p1["signal_conflict"]) is True
    assert p1["signal_count"]==2
    assert out.set_index("player_id").loc[2,"availability"]=="suspended"

def test_unknown_status_is_explicit_and_missing_news_can_be_represented():
    signals=frame([(3,"rumour","2026-08-18T11:00:00Z","news")])
    out=normalize_signals(signals,DEADLINE)
    assert out.iloc[0]["availability"]=="unknown"
    assert out.iloc[0]["priority"]==0

def test_doubtful_and_return_from_injury():
    signals=frame([(4,"doubtful","2026-08-18T10:00:00Z","club"),(5,"fit","2026-08-18T10:00:00Z","club")])
    out=normalize_signals(signals,DEADLINE)
    assert out.set_index("player_id").loc[4,"availability"]=="doubtful"
    assert out.set_index("player_id").loc[5,"availability"]=="available"

@pytest.mark.parametrize("timestamp",["2026-08-15T00:00:00Z","2026-08-18T13:00:00Z"])
def test_stale_or_post_deadline_signals_are_rejected(timestamp):
    with pytest.raises(ValueError):
        normalize_signals(frame([(1,"available",timestamp,"news")]),DEADLINE,max_age_hours=72)

def test_signal_timestamps_are_required_and_invalid_values_fail():
    with pytest.raises(ValueError,match="Missing signal columns"):
        normalize_signals(pd.DataFrame({"player_id":[1],"status":["available"]}),DEADLINE)
    with pytest.raises(ValueError,match="Invalid signal_timestamp"):
        normalize_signals(frame([(1,"available","not-a-time","news")]),DEADLINE)
