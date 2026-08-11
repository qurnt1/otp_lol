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
class GameLoading(CoreEvent):
    """The client started loading the match after champion select."""


@dataclass(frozen=True, slots=True)
class GameStarted(CoreEvent):
    """The game reached the playable in-progress phase."""


@dataclass(frozen=True, slots=True)
class ReturnedToLobby(CoreEvent):
    """The client returned to the lobby after a completed match."""


@dataclass(frozen=True, slots=True)
class SummonerUpdated(CoreEvent):
    """The detected Riot ID changed."""

    riot_id: str | None


@dataclass(frozen=True, slots=True)
class RankedEntry:
    """One ranked queue entry returned by the LCU ranked-stats endpoint.

    Missing or malformed LCU fields remain ``None``.  The core never derives a
    tier, division, LP value, or record from another source.
    """

    queue_type: str
    tier: str | None = None
    division: str | None = None
    league_points: int | None = None
    wins: int | None = None
    losses: int | None = None
    is_provisional: bool | None = None


@dataclass(frozen=True, slots=True)
class ProfileUpdated(CoreEvent):
    """The current LCU profile snapshot needed by downstream surfaces.

    ``profile_icon_id`` is the authoritative LCU avatar identifier.  It is an
    identifier rather than a fabricated URL or image, so a presentation layer
    can resolve it through its existing asset conventions.  ``ranked_entries``
    is empty when the LCU endpoint is unavailable or returns no valid queue.
    """

    riot_id: str | None
    summoner_id: int | None
    puuid: str | None
    profile_icon_id: int | None
    summoner_level: int | None
    ranked_entries: tuple[RankedEntry, ...] = ()


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
