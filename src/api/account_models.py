"""Typed API DTOs for normalized LCU account statistics."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field


class AccountSummary(BaseModel):
    level: int | None = None
    profile_icon_id: int | None = None
    xp_since_last_level: int | None = None
    xp_until_next_level: int | None = None


class RankedQueue(BaseModel):
    queue_type: str
    tier: str | None = None
    division: str | None = None
    league_points: int | None = None
    wins: int | None = None
    losses: int | None = None


class RankedStats(BaseModel):
    queues: list[RankedQueue]


class ChampionMastery(BaseModel):
    champion_id: int
    level: int | None = None
    points: int | None = None
    last_play_time: int | None = None
    chest_granted: bool | None = None


class MasteryStats(BaseModel):
    champions: list[ChampionMastery]
    score: int | None = None


class ChallengeProgress(BaseModel):
    id: int
    value: int | None = None
    percentile: float | None = None
    level: str | None = None
    category: str | None = None


class ChallengeSummary(BaseModel):
    challenges: list[ChallengeProgress]
    total_points: int | None = None


class ChallengeCategory(BaseModel):
    category: str
    current: int | None = None
    max: int | None = None
    percentile: float | None = None


class ChallengesStats(BaseModel):
    challenges: ChallengeSummary
    categories: list[ChallengeCategory]


class MatchSummary(BaseModel):
    game_id: str
    creation: int | None = None
    duration: int | None = None
    queue_id: int | None = None
    queue_name: str | None = None
    map_name: str | None = None
    champion_id: int | None = None
    win: bool | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None


class MatchHistory(BaseModel):
    offset: int
    matches: list[MatchSummary]
    total: int | None = None


class MatchParticipant(BaseModel):
    champion_id: int | None = None
    team_id: int | None = None
    win: bool | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    gold_earned: int | None = None
    total_minions_killed: int | None = None
    vision_score: int | None = None
    items: list[int] = Field(default_factory=list)


class MatchDetail(BaseModel):
    game_id: str
    creation: int | None = None
    duration: int | None = None
    queue_id: int | None = None
    queue_name: str | None = None
    map_name: str | None = None
    participants: list[MatchParticipant]
    item_names: dict[int, str] = Field(default_factory=dict)


class TimelineEvent(BaseModel):
    type: str
    timestamp: int
    participant_id: int | None = None
    killer_id: int | None = None
    victim_id: int | None = None
    item_id: int | None = None
    skill_slot: int | None = None
    assisting_participant_ids: list[int] = Field(default_factory=list)


class MatchTimeline(BaseModel):
    game_id: str
    events: list[TimelineEvent]
    item_names: dict[int, str] = Field(default_factory=dict)


T = TypeVar("T")


class AccountResult(BaseModel, Generic[T]):
    data: T | None = None
    available: bool
    stale: bool
    last_synced: str | None = None
    error: str | None = None
    source: Literal["lcu", "cache", "mixed", "unavailable"]
    from_cache: bool
    errors: dict[str, str]
