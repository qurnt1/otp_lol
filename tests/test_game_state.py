"""Verify GameState reset_between_games covers all transient fields."""

from dataclasses import MISSING, fields

from src.core.game_state import GameState


def test_all_transient_fields_are_reset():
    """Every field marked transient must be restored to its default by reset_between_games."""
    state = GameState()

    # Modify every transient field to a non-default value
    for f in fields(GameState):
        if not f.metadata.get("transient"):
            continue
        if f.type == "bool" or f.type == bool:
            setattr(state, f.name, True)
        elif f.type == "int" or f.type == int:
            setattr(state, f.name, 999)
        elif f.type == "float" or f.type == float:
            setattr(state, f.name, 99.9)
        elif f.type == "str" or f.type == str:
            setattr(state, f.name, "modified")
        else:
            setattr(state, f.name, None)

    state.reset_between_games()

    for f in fields(GameState):
        if not f.metadata.get("transient"):
            continue
        if f.default is not MISSING:
            expected = f.default
        elif f.default_factory is not MISSING:
            expected = f.default_factory()
        else:
            continue
        actual = getattr(state, f.name)
        assert actual == expected, (
            f"Field {f.name!r} was not reset: expected {expected!r}, got {actual!r}"
        )


def test_persistent_fields_are_not_reset():
    """Persistent fields must keep their values after reset_between_games."""
    state = GameState()

    # Set known values on persistent fields
    state.current_phase = "ChampSelect"
    state.summoner = "TestPlayer"
    state.summoner_id = 12345
    state.platform_routing = "na1"
    state.region_routing = "americas"

    state.reset_between_games()

    assert state.current_phase == "ChampSelect"
    assert state.summoner == "TestPlayer"
    assert state.summoner_id == 12345
    assert state.platform_routing == "na1"
    assert state.region_routing == "americas"


def test_reset_between_games_covers_all_fields():
    """Every GameState field must be classified as either persistent or transient."""
    transient_fields = {f.name for f in fields(GameState) if f.metadata.get("transient")}
    persistent_fields = {
        "current_phase",
        "current_queue_id",
        "summoner",
        "summoner_id",
        "puuid",
        "auto_game_name",
        "auto_tag_line",
        "platform_routing",
        "region_routing",
        "last_game_start_notify_ts",
        "last_reported_summoner",
        "cache_lock",
    }
    all_fields = {f.name for f in fields(GameState)}
    unclassified = all_fields - transient_fields - persistent_fields
    assert not unclassified, (
        f"Unclassified fields (add them as transient or persistent): {unclassified}"
    )
