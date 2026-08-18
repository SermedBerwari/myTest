import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def load(name, path):
    spec=importlib.util.spec_from_file_location(name, ROOT/path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

class FixedDateTime:
    @classmethod
    def now(cls, tz=None):
        return datetime(2026,8,18,8,57,18,tzinfo=timezone.utc)

def test_bootstrap_writer_is_write_once(tmp_path, monkeypatch):
    m=load("fetch_bootstrap", "scripts/fetch_bootstrap.py")
    monkeypatch.setattr(m,"OUTPUT_DIR",tmp_path); monkeypatch.setattr(m,"datetime",FixedDateTime)
    data={"elements":[],"teams":[],"events":[],"element_types":[]}
    first=m.save_bootstrap(data); before=first.read_bytes()
    try: m.save_bootstrap({"changed":True})
    except FileExistsError: pass
    else: raise AssertionError("bootstrap writer overwrote an immutable snapshot")
    assert first.read_bytes()==before

def test_fixtures_writer_is_write_once(tmp_path, monkeypatch):
    m=load("fetch_fixtures", "scripts/fetch_fixtures.py")
    monkeypatch.setattr(m,"OUTPUT_DIR",tmp_path); monkeypatch.setattr(m,"datetime",FixedDateTime)
    first=m.save_fixtures([]); before=first.read_bytes()
    try: m.save_fixtures([{"changed":True}])
    except FileExistsError: pass
    else: raise AssertionError("fixtures writer overwrote an immutable snapshot")
    assert first.read_bytes()==before

def test_player_history_writer_is_write_once(tmp_path):
    m=load("fetch_player_history", "scripts/fetch_player_history.py")
    m.PLAYERS_DIR=tmp_path
    first=m.save_player_history(1,{"history":[]},"2026-08-18_08-57-18"); before=first.read_bytes()
    try: m.save_player_history(1,{"changed":True},"2026-08-18_08-57-18")
    except FileExistsError: pass
    else: raise AssertionError("player-history writer overwrote an immutable snapshot")
    assert first.read_bytes()==before
