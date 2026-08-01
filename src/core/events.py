"""Immutable events shared across the core, application, and desktop layers."""

from dataclasses import dataclass


class RuntimeEvent:
    """Marker base class accepted by the desktop event bridge."""

    __slots__ = ()


class CoreEvent(RuntimeEvent):
    """Marker base class for events emitted by the LCU runtime core."""

    __slots__ = ()


class ApplicationEvent(RuntimeEvent):
    """Marker base class for events emitted by application orchestration."""

    __slots__ = ()


@dataclass(frozen=True, slots=True)
class Connected(CoreEvent):
    """The League client connection is ready."""


@dataclass(frozen=True, slots=True)
class Disconnected(CoreEvent):
    """The League client connection ended or temporarily became unavailable."""

    transient: bool
    reason: str


@dataclass(frozen=True, slots=True)
class StatusChanged(CoreEvent):
    """A user-facing runtime status changed."""

    message: str
    category: str = ""


@dataclass(frozen=True, slots=True)
class PhaseChanged(CoreEvent):
    """The League gameflow phase changed."""

    phase: str


@dataclass(frozen=True, slots=True)
class SummonerUpdated(CoreEvent):
    """The detected Riot ID changed."""

    riot_id: str | None


@dataclass(frozen=True, slots=True)
class ChampionPicked(CoreEvent):
    """A configured champion was locked in."""

    champion: str


@dataclass(frozen=True, slots=True)
class ChampionBanned(CoreEvent):
    """A configured champion was banned."""

    champion: str


@dataclass(frozen=True, slots=True)
class SpellsApplied(CoreEvent):
    """Summoner spells were applied to the active champion-select slot."""

    first: str
    second: str


@dataclass(frozen=True, slots=True)
class PlayAgainSucceeded(CoreEvent):
    """The post-game play-again action succeeded."""


@dataclass(frozen=True, slots=True)
class ReadyCheckAccepted(CoreEvent):
    """The ready check was accepted automatically."""


@dataclass(frozen=True, slots=True)
class ToastRequested(ApplicationEvent):
    """Application orchestration requested a transient message."""

    message: str
    duration_ms: int = 2000


@dataclass(frozen=True, slots=True)
class UpdateAvailable(ApplicationEvent):
    """A newer release is available."""

    version: str
    highlights: str
