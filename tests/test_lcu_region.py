import asyncio

from src.lcu.region import (
    detect_account_routing,
    normalize_provider_region,
    normalize_region_identity,
    platform_to_provider_region,
    platform_to_regional_routing,
)


class _Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    async def json(self):
        return self.payload


class _Connection:
    def __init__(self, responses):
        self.responses = responses
        self.paths = []

    async def request(self, method, path):
        self.paths.append(path)
        response = self.responses.get(path)
        return response if isinstance(response, _Response) else _Response(response, 200) if response is not None else _Response({}, 404)


def test_region_matrix_normalizes_provider_and_regional_values():
    assert normalize_region_identity("EUW1", source="test") == normalize_region_identity("euw", source="test")
    expected = {
        "euw": ("euw1", "europe"), "eune": ("eun1", "europe"), "na": ("na1", "americas"),
        "kr": ("kr", "asia"), "jp": ("jp1", "asia"), "br": ("br1", "americas"),
        "lan": ("la1", "americas"), "las": ("la2", "americas"), "oce": ("oc1", "sea"),
        "tr": ("tr1", "europe"), "ru": ("ru", "europe"),
    }
    for region, (platform, routing) in expected.items():
        identity = normalize_region_identity(region, source="matrix")
        assert identity is not None
        assert (identity.platform_id, identity.provider_region, identity.regional_routing) == (platform, region, routing)
    identity = normalize_region_identity("na1", source="test")
    assert identity is not None
    assert (identity.platform_id, identity.provider_region, identity.regional_routing) == ("na1", "na", "americas")
    assert normalize_provider_region("KR") == "kr"
    assert platform_to_provider_region("EUW1") == "euw"
    assert platform_to_regional_routing("oce") == "sea"


def test_detection_prefers_platform_config_over_fallbacks():
    connection = _Connection({
        "/lol-platform-config/v1/namespaces/LoginDataPacket/platformId": "eun1",
        "/rso-auth/v1/authorization": {"currentPlatformId": "na1"},
    })
    identity = asyncio.run(detect_account_routing(connection))
    assert identity is not None
    assert (identity.platform_id, identity.provider_region, identity.regional_routing, identity.source) == ("eun1", "eune", "europe", "platform_config")
    assert connection.paths == ["/lol-platform-config/v1/namespaces/LoginDataPacket/platformId"]


def test_detection_uses_region_locale_then_command_line():
    locale_connection = _Connection({"/riotclient/region-locale": {"region": "kr"}})
    locale_identity = asyncio.run(detect_account_routing(locale_connection))
    assert locale_identity is not None
    assert (locale_identity.platform_id, locale_identity.provider_region, locale_identity.regional_routing, locale_identity.source) == ("kr", "kr", "asia", "region_locale")

    args_connection = _Connection({"/riotclient/command-line-args": {"args": ["--region=EUW"]}})
    args_identity = asyncio.run(detect_account_routing(args_connection))
    assert args_identity is not None
    assert (args_identity.platform_id, args_identity.provider_region, args_identity.regional_routing, args_identity.source) == ("euw1", "euw", "europe", "command_line_args")


def test_detection_returns_none_when_all_sources_are_unavailable():
    assert asyncio.run(detect_account_routing(_Connection({}))) is None
