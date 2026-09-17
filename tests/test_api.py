import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from fastapi.testclient import TestClient
from PIL import Image
from starlette.websockets import WebSocketDisconnect

from src.config import CONFIG_SCHEMA_VERSION, CURRENT_VERSION, DEMO_PARAMS, FIRST_LAUNCH_PARAMS
from src.config import settings as settings_module
from src.domain.events import EventBroker

with tempfile.TemporaryDirectory(prefix="otp-lol-api-import-") as api_import_dir:
    with patch.object(settings_module, "PARAMETERS_PATH", str(Path(api_import_dir) / "parameters.toml")):
        from src.api.context import ApplicationContext
        from src.api.app import create_app


class EventBrokerTests(unittest.IsolatedAsyncioTestCase):
    async def test_events_published_from_worker_thread_reach_subscriber(self):
        broker = EventBroker()
        subscription = broker.subscribe()

        worker = threading.Thread(target=broker.publish, args=("phase_change", "ChampSelect"))
        worker.start()
        worker.join()

        event = await asyncio.wait_for(subscription.next_event(), timeout=1)
        subscription.close()

        self.assertEqual(event.type, "phase_change")
        self.assertEqual(event.data, "ChampSelect")
        self.assertEqual(broker.subscriber_count, 0)

    async def test_publish_prunes_subscription_when_consumer_loop_is_closed(self):
        broker = EventBroker()
        subscription = broker.subscribe()
        closed_loop = asyncio.new_event_loop()
        closed_loop.close()
        subscription._loop = closed_loop

        broker.publish("toast", "ignored")

        self.assertEqual(broker.subscriber_count, 0)


class ApiBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.context = ApplicationContext(params=DEMO_PARAMS)
        self.context.data_dragon.loaded = True
        self.context.data_dragon.version = "16.18.1"
        self.context.data_dragon.by_id = {
            86: {
                "name": "Garen",
                "id": "Garen",
                "key": "86",
                "tags": ["Fighter"],
                "image": {"full": "Garen.png"},
            }
        }
        self.context.data_dragon.name_by_id = {86: "Garen"}
        self.context.data_dragon.by_norm_name = {"garen": 86}
        self.context.data_dragon.all_names = ["Garen"]
        self.context.data_dragon.summoner_loaded = True
        self.context.data_dragon.summoner_data = {"Flash": "SummonerFlash.png"}
        self.context.save = lambda: True
        self.client = TestClient(create_app(self.context), headers={"Origin": "http://testserver"})

    def test_cross_origin_cannot_trigger_settings_reset(self):
        before = self.context.get_params()

        response = self.client.post(
            "/api/settings/reset",
            headers={"Origin": "https://provider.example"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Untrusted request origin"})
        self.assertEqual(self.context.get_params(), before)

    def test_health_and_runtime_do_not_expose_lcu_credentials(self):
        health = self.client.get("/api/health")
        runtime = self.client.get("/api/runtime")

        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["ok"])
        self.assertEqual(runtime.status_code, 200)
        self.assertIn("connected", runtime.json())
        self.assertEqual(runtime.json()["version"], CURRENT_VERSION)
        self.assertNotIn("password", runtime.text.lower())

    def test_bootstrap_is_local_only_and_contains_the_three_initial_snapshots(self):
        response = self.client.get("/api/bootstrap")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"runtime", "settings", "presets", "preset_previews", "ban_preview"})
        self.assertEqual(response.json()["presets"]["slots"]["pick_1"]["champion"], "Garen")
        self.assertEqual(response.json()["preset_previews"]["pick_1"]["champion_id"], 86)
        self.assertEqual(response.json()["preset_previews"]["pick_1"]["skin_preview_url"], "/api/assets/skins/86/86013/splash?skin_num=13&v=16.18.1")
        self.assertNotIn('"catalog"', response.text)

    def test_metadata_reports_loaded_data_dragon_version(self):
        response = self.client.get("/api/metadata")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data_dragon_version"], "16.18.1")

    def test_catalog_asset_urls_are_versioned(self):
        champions = self.client.get("/api/champions")
        spells = self.client.get("/api/spells")
        flash = next(item for item in spells.json()["items"] if item["name"] == "Flash")

        self.assertEqual(champions.json()["items"][0]["icon_url"], "/api/assets/champions/86.png?v=16.18.1")
        self.assertEqual(champions.json()["items"][0]["splash_url"], "/api/assets/champions/86/splash?v=16.18.1")
        self.assertEqual(flash["icon_url"], "/api/assets/spells?name=Flash&v=16.18.1")

    def test_bootstrap_preview_does_not_load_skin_catalogue(self):
        with patch.object(self.context.data_dragon, "get_skin_catalog", side_effect=AssertionError("catalogue loaded")):
            response = self.client.get("/api/bootstrap")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["preset_previews"]["pick_1"]["skin_name"], "God-King Garen")

    def test_skin_preview_asset_does_not_load_skin_catalogue(self):
        preview = Image.new("RGBA", (4, 4))
        with (
            patch.object(self.context, "ensure_data_dragon", new_callable=AsyncMock) as ensure,
            patch.object(self.context.data_dragon, "get_skin_catalog", side_effect=AssertionError("catalogue loaded")),
            patch.object(self.context.data_dragon, "get_cached_skin_catalog", return_value=[]),
            patch.object(self.context.data_dragon, "get_skin_preview", return_value=preview) as get_skin_preview,
        ):
            response = self.client.get("/api/assets/skins/86/86013.png?skin_num=13")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.headers["cache-control"], "no-cache")
        ensure.assert_awaited_once()
        get_skin_preview.assert_called_once_with(86, 13)

    def test_skin_splash_asset_prefers_centered_splash_and_falls_back_in_order(self):
        preview = Image.new("RGBA", (4, 4))
        skin = {
            "skin_id": 86013,
            "centered_splash_url": "https://cdn.example/centered.jpg",
            "uncentered_splash_url": "https://cdn.example/uncentered.jpg",
            "splash_url": "https://cdn.example/splash.jpg",
            "tile_url": "https://cdn.example/tile.jpg",
        }
        with (
            patch.object(self.context, "ensure_data_dragon", new_callable=AsyncMock) as ensure,
            patch.object(self.context.data_dragon, "get_skin_catalog", side_effect=AssertionError("catalogue loaded")),
            patch.object(self.context.data_dragon, "get_cached_skin_catalog", return_value=[skin]),
            patch.object(
                self.context.data_dragon,
                "get_remote_image",
                side_effect=[None, None, None, preview],
            ) as get_remote_image,
        ):
            response = self.client.get("/api/assets/skins/86/86013/splash?skin_num=13")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        ensure.assert_awaited_once()
        self.assertEqual(
            [call.args[0] for call in get_remote_image.call_args_list],
            [
                "https://cdn.example/centered.jpg",
                "https://cdn.example/uncentered.jpg",
                "https://cdn.example/splash.jpg",
                "https://cdn.example/tile.jpg",
            ],
        )

    def test_skin_splash_asset_uses_skin_number_without_loading_catalogue(self):
        preview = Image.new("RGBA", (4, 4))
        with (
            patch.object(self.context, "ensure_data_dragon", new_callable=AsyncMock) as ensure,
            patch.object(self.context.data_dragon, "get_skin_catalog", side_effect=AssertionError("catalogue loaded")),
            patch.object(self.context.data_dragon, "get_cached_skin_catalog", return_value=[]),
            patch.object(self.context.data_dragon, "get_skin_preview", return_value=preview) as get_skin_preview,
        ):
            response = self.client.get("/api/assets/skins/86/86013/splash?skin_num=13")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        ensure.assert_awaited_once()
        get_skin_preview.assert_called_once_with(86, 13)

    def test_settings_import_rejects_unknown_fields(self):
        response = self.client.post("/api/settings/import", json={"not_a_setting": True})

        self.assertEqual(response.status_code, 422)

    def test_settings_import_requires_the_current_schema(self):
        missing_version = self.client.post("/api/settings/import", json={"theme": "flatly"})
        old_version = self.client.post("/api/settings/import", json={"config_schema_version": 5, "theme": "flatly"})
        current_version = self.client.post("/api/settings/import", json={
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "theme": "flatly",
        })

        self.assertEqual(missing_version.status_code, 422)
        self.assertEqual(old_version.status_code, 422)
        self.assertEqual(current_version.status_code, 200)

    def test_settings_export_import_and_reset_are_real_persistent_operations(self):
        exported = self.client.get("/api/settings/export")
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.headers["content-disposition"], 'attachment; filename="otp-lol-settings.json"')

        self.assertEqual(self.client.patch("/api/settings", json={"theme": "flatly"}).status_code, 200)
        imported = self.client.post("/api/settings/import", json={
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "theme": "darkly",
        })
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.json()["theme"], "darkly")

        reset = self.client.post("/api/settings/reset")
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reset.json()["theme"], "darkly")

    def test_settings_patch_is_persisted_in_context(self):
        response = self.client.patch("/api/settings", json={"presets_enabled": False})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["presets_enabled"])
        self.assertFalse(self.context.get_params()["presets_enabled"])

    def test_settings_matrix_persists_every_frontend_editable_setting(self):
        save = Mock(return_value=True)
        self.context.save = save
        values = {
            "auto_accept_enabled": False,
            "auto_pick_enabled": False,
            "auto_ban_enabled": False,
            "auto_summoners_enabled": False,
            "presets_enabled": False,
            "selected_pick_1": "",
            "selected_pick_2": "",
            "selected_pick_3": "",
            "selected_ban": "",
            "theme": "flatly",
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Tester#EUW",
            "manual_region": "na",
            "preferred_stats_site": "deeplol",
            "preferred_hotkey_site": "opgg",
            "hotkey_toggle_window": "ctrl+alt+c",
            "hotkey_open_site": "ctrl+alt+p",
            "auto_play_again_enabled": True,
            "auto_hide_on_connect": False,
            "close_app_on_lol_exit": False,
            "ignored_update_version": "11.0",
            "skin_automation_enabled": False,
            "window_x": 24,
            "window_y": 48,
            "window_width": 1440,
            "window_height": 900,
            "window_maximized": True,
        }

        for key, value in values.items():
            response = self.client.patch("/api/settings", json={key: value})
            self.assertEqual(response.status_code, 200, key)
            self.assertEqual(response.json()[key], value, key)
            self.assertEqual(self.context.get_params()[key], value, key)

        self.assertGreaterEqual(save.call_count, len(values))

    def test_unknown_settings_are_rejected(self):
        response = self.client.patch("/api/settings", json={"unknown_setting": True})
        old_skin_modes = self.client.patch("/api/settings", json={"main_skin_mode_override": "inherit"})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(old_skin_modes.status_code, 422)

    def test_settings_patch_rejects_invalid_or_duplicate_hotkeys(self):
        invalid = self.client.patch("/api/settings", json={"hotkey_toggle_window": "ctrl"})
        duplicate = self.client.patch("/api/settings", json={"hotkey_toggle_window": "alt+p"})

        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(duplicate.status_code, 422)

    def test_settings_patch_rejects_arming_presets_without_a_pick(self):
        self.context.update_parameters({
            "presets_enabled": False,
            "selected_pick_1": "",
            "selected_pick_2": "",
            "selected_pick_3": "",
        })

        response = self.client.patch("/api/settings", json={"presets_enabled": True})

        self.assertEqual(response.status_code, 422)
        self.assertFalse(self.context.get_params()["presets_enabled"])

    def test_settings_patch_rejects_clearing_last_pick_while_presets_are_armed(self):
        self.context.update_parameters({
            "presets_enabled": True,
            "selected_pick_1": "Garen",
            "selected_pick_2": "",
            "selected_pick_3": "",
        })

        response = self.client.patch(
            "/api/settings",
            json={"selected_pick_1": "", "selected_pick_2": "", "selected_pick_3": ""},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.context.get_params()["selected_pick_1"], "Garen")

    def test_settings_patch_rolls_back_when_persistence_fails(self):
        self.context.save = lambda: False

        response = self.client.patch("/api/settings", json={"theme": "flatly"})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.context.get_params()["theme"], "darkly")

    def test_preset_patch_updates_selected_champion(self):
        response = self.client.put("/api/presets/pick_2", json={"champion": "Ahri"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slots"]["pick_2"]["champion"], "Ahri")
        self.assertEqual(self.context.get_params()["selected_pick_2"], "Ahri")

    def test_preset_patch_rejects_unknown_spell(self):
        response = self.client.put("/api/presets/pick_1", json={"spell_1": "NotASpell"})

        self.assertEqual(response.status_code, 422)

    def test_preset_patch_rejects_negative_skin_id(self):
        response = self.client.put("/api/presets/pick_1", json={"skin_id": -1})

        self.assertEqual(response.status_code, 422)

    def test_preset_patch_rejects_duplicate_spells(self):
        response = self.client.put(
            "/api/presets/pick_1",
            json={"spell_1": "Flash", "spell_2": "Flash"},
        )

        self.assertEqual(response.status_code, 422)

    def test_events_websocket_receives_runtime_events(self):
        with self.client.websocket_connect("/api/events") as websocket:
            snapshot = websocket.receive_json()
            self.assertEqual(snapshot["type"], "runtime_snapshot")
            self.assertIn("timestamp", snapshot)

            publisher = threading.Thread(target=self.context.broker.publish, args=("toast", "Hello"))
            publisher.start()
            publisher.join()

            event = websocket.receive_json()
            self.assertEqual(event["type"], "toast")
            self.assertEqual(event["data"], "Hello")

    def test_websocket_rejects_external_origin(self):
        with self.assertRaises(WebSocketDisconnect), self.client.websocket_connect(
            "/api/events",
            headers={"origin": "https://evil.example"},
        ):
            pass

    def test_http_responses_include_local_security_headers(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        policy = response.headers["content-security-policy"]
        self.assertIn("default-src 'self'", policy)
        frame_src = next(directive for directive in policy.split("; ") if directive.startswith("frame-src "))
        self.assertEqual(frame_src, "frame-src 'self' https://www.deeplol.gg")
        self.assertNotIn("frame-src *", policy)
        self.assertNotIn("op.gg", frame_src)
        self.assertNotIn("leagueofgraphs", frame_src)

    def test_auto_detection_does_not_use_manual_account_when_league_is_closed(self):
        self.context.params.update({
            "summoner_name_auto_detect": True,
            "manual_summoner_name": "Player#TAG",
            "manual_region": "na",
            "preferred_stats_site": "deeplol",
        })
        snapshot = SimpleNamespace(connected=False, riot_id="", region="")
        with patch.object(self.context.runtime, "snapshot", return_value=snapshot):
            response = self.client.get("/api/links/stats")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "available": False,
            "site": "deeplol",
            "url": None,
            "homepage_url": "https://www.deeplol.gg/",
            "riot_id": None,
            "region": None,
            "embed_allowed": True,
        })

    def test_stats_link_uses_manual_account_only_when_manual_mode_is_enabled(self):
        self.context.params.update({
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "Player#TAG",
            "manual_region": "na",
            "preferred_stats_site": "deeplol",
        })

        response = self.client.get("/api/links/stats")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["url"], "https://www.deeplol.gg/summoner/na/Player-TAG")
        self.assertEqual(response.json()["riot_id"], "Player#TAG")

    def test_stats_link_uses_connected_auto_detected_account_over_manual_fallback(self):
        self.context.params.update({
            "summoner_name_auto_detect": True,
            "manual_summoner_name": "Saved#Manual",
            "manual_region": "na",
            "preferred_stats_site": "dpm",
        })
        snapshot = SimpleNamespace(connected=True, riot_id="Live#EUW", region="euw")
        with patch.object(self.context.runtime, "snapshot", return_value=snapshot):
            response = self.client.get("/api/links/stats")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "available": True,
            "site": "dpm",
            "url": "https://dpm.lol/Live-EUW/",
            "homepage_url": "https://dpm.lol/",
            "riot_id": "Live#EUW",
            "region": "euw",
            "embed_allowed": False,
        })

    def test_stats_link_does_not_use_stale_detected_account_when_disconnected(self):
        self.context.params.update({
            "summoner_name_auto_detect": True,
            "auto_detected_riot_id": "Stale#TAG",
            "manual_summoner_name": "",
            "preferred_stats_site": "leagueofgraphs",
        })
        snapshot = SimpleNamespace(connected=False, riot_id="", region="")
        with patch.object(self.context.runtime, "snapshot", return_value=snapshot):
            response = self.client.get("/api/links/stats")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "available": False,
            "site": "leagueofgraphs",
            "url": None,
            "homepage_url": "https://www.leagueofgraphs.com/",
            "riot_id": None,
            "region": None,
            "embed_allowed": False,
        })

    def test_provider_catalog_is_the_single_source_for_frontend_options(self):
        response = self.client.get("/api/catalog/providers")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stats"][0], {
            "id": "opgg",
            "label": "OP.GG",
            "logo_url": "/api/assets/providers/opgg",
        })
        self.assertEqual([provider["id"] for provider in response.json()["live"]], ["porofessor", "deeplol", "dpm", "opgg"])
        self.assertIn({"id": "euw", "label": "EUW"}, response.json()["regions"])

    def test_provider_logo_endpoint_only_serves_known_local_assets(self):
        logo = self.client.get("/api/assets/providers/opgg")
        unknown = self.client.get("/api/assets/providers/unknown")

        self.assertEqual(logo.status_code, 200)
        self.assertEqual(logo.headers["content-type"], "image/png")
        self.assertTrue(logo.content.startswith(b"\x89PNG"))
        self.assertEqual(unknown.status_code, 404)

    def test_live_link_uses_configured_live_provider_and_auto_detected_account(self):
        self.context.params.update({"summoner_name_auto_detect": True, "preferred_hotkey_site": "deeplol"})
        snapshot = SimpleNamespace(connected=True, riot_id="Live#EUW", region="euw")
        with patch.object(self.context.runtime, "snapshot", return_value=snapshot):
            response = self.client.get("/api/links/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "available": True,
            "site": "deeplol",
            "url": "https://www.deeplol.gg/summoner/euw/Live-EUW/ingame",
            "homepage_url": "https://www.deeplol.gg/",
            "riot_id": "Live#EUW",
            "region": "euw",
            "embed_allowed": False,
        })

    def test_live_link_uses_manual_account_and_safe_homepage_without_an_account(self):
        self.context.params.update({
            "summoner_name_auto_detect": False,
            "manual_summoner_name": "",
            "manual_region": "euw",
            "preferred_hotkey_site": "dpm",
        })

        response = self.client.get("/api/links/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "available": False,
            "site": "dpm",
            "url": None,
            "homepage_url": "https://dpm.lol/",
            "riot_id": None,
            "region": None,
            "embed_allowed": False,
        })

    def test_catalog_routes_use_loaded_metadata_and_report_lcu_absence(self):
        champions = self.client.get("/api/champions?q=garen")
        spells = self.client.get("/api/spells")
        runes = self.client.get("/api/runes")

        self.assertEqual(champions.status_code, 200)
        self.assertEqual(champions.json()["items"][0]["name"], "Garen")
        self.assertEqual(champions.json()["items"][0]["roles"], ["MIDDLE", "TOP"])
        self.assertEqual(spells.status_code, 200)
        self.assertIn("Flash", {item["name"] for item in spells.json()["items"]})
        self.assertEqual(runes.status_code, 200)
        self.assertFalse(runes.json()["available"])

    def test_catalog_uses_local_asset_urls_and_serves_cached_images(self):
        with patch.object(self.context.data_dragon, "get_champion_icon", return_value=Image.new("RGBA", (4, 4))):
            champions = self.client.get("/api/champions?q=garen")
            image = self.client.get("/api/assets/champions/86.png")

        self.assertEqual(champions.json()["items"][0]["icon_url"], "/api/assets/champions/86.png?v=16.18.1")
        self.assertEqual(champions.json()["items"][0]["splash_url"], "/api/assets/champions/86/splash?v=16.18.1")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers["content-type"], "image/png")
        self.assertTrue(image.content.startswith(b"\x89PNG"))

    def test_champion_splash_route_uses_the_datadragon_cache_boundary(self):
        with patch.object(self.context.data_dragon, "get_champion_splash", return_value=Image.new("RGBA", (8, 4))):
            response = self.client.get("/api/assets/champions/86/splash")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")

    def test_spell_asset_route_uses_the_datadragon_cache_boundary(self):
        with patch.object(self.context.data_dragon, "get_summoner_icon", return_value=Image.new("RGBA", (4, 4))):
            response = self.client.get("/api/assets/spells?name=Flash")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")

    def test_rune_perk_asset_route_accepts_only_validated_lcu_paths(self):
        with patch.object(self.context.data_dragon, "get_rune_perk_icon", return_value=Image.new("RGBA", (4, 4))) as get_icon:
            response = self.client.get(
                "/api/assets/runes/perk",
                params={"path": "lol-game-data/assets/ux/cherry/perks/precision.png"},
            )
            rejected = self.client.get(
                "/api/assets/runes/perk",
                params={"path": "https://evil.example/perk.png"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(rejected.status_code, 404)
        get_icon.assert_called_once_with("lol-game-data/assets/ux/cherry/perks/precision.png")

    def test_skin_catalog_falls_back_to_splash_when_tile_is_missing(self):
        self.context.runtime.get_skin_catalog = AsyncMock(return_value=[
            {
                "skin_id": 86013,
                "tile_url": None,
                "centered_splash_url": "/fallback/splash.jpg",
                "uncentered_splash_url": None,
                "splash_url": "https://example.test/splash.jpg",
            }
        ])

        response = self.client.get("/api/skins/86")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["catalog"][0]["tile_url"], "/api/assets/skins/86/86013.png?v=16.18.1")

    def test_rune_catalog_uses_local_style_and_perk_asset_urls(self):
        with patch.object(type(self.context.runtime), "is_active", new_callable=PropertyMock, return_value=True):
            self.context.runtime.fetch_rune_pages = AsyncMock(return_value=[
                {
                    "id": 1001,
                    "name": "Test Rune Page",
                    "primaryStyleId": 8000,
                    "subStyleId": 8400,
                    "selectedPerkIds": [8005, 8008, 8002, 8003, 8401, 8410, 5001, 5002, 5003],
                    "current": True,
                }
            ])
            self.context.runtime.fetch_rune_styles = AsyncMock(return_value={
                8000: {
                    "name": "Precision",
                    "iconPath": "/styles/precision.png",
                    "perks": [{"id": 8005, "name": "Press the Attack", "iconPath": "/perks/press.png"}],
                },
                8400: {"name": "Resolve", "iconPath": "/styles/resolve.png", "perks": []},
            })

            response = self.client.get("/api/runes")

        page = response.json()["pages"][0]
        styles = response.json()["styles"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(page["selectedPerkPaths"][0], "/perks/press.png")
        self.assertEqual(styles["8000"]["icon_url"], "/api/assets/runes/style?path=/styles/precision.png")
        self.assertEqual(styles["8000"]["perks"][0]["icon_url"], "/api/assets/runes/perk/8005.png")

    @patch(
        "src.api.routes.runtime.check_for_updates",
        return_value={"version": "12.0", "release_url": "https://example.test/release"},
    )
    def test_updates_route_exposes_new_release_and_honors_ignored_version(self, _check_for_updates):
        response = self.client.get("/api/updates")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["available"])
        self.assertEqual(response.json()["update"]["version"], "12.0")

        self.context.update_param("ignored_update_version", "12.0")
        ignored = self.client.get("/api/updates")
        self.assertFalse(ignored.json()["available"])

    def test_frontend_static_mount_serves_index(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "index.html").write_text("<h1>OTP LOL</h1>", encoding="utf-8")
            app = create_app(self.context, frontend_dir=directory)
            response = TestClient(app).get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("OTP LOL", response.text)


if __name__ == "__main__":
    unittest.main()
