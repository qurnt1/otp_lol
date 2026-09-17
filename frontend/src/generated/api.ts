// Generated from FastAPI. Do not edit by hand.
export interface paths {
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runtime": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Runtime Snapshot */
        get: operations["runtime_snapshot_api_runtime_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/bootstrap": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Bootstrap
         * @description Return only persisted/runtime state, never a remote catalogue.
         */
        get: operations["bootstrap_api_bootstrap_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/metadata": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Metadata */
        get: operations["metadata_api_metadata_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/updates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Updates */
        get: operations["updates_api_updates_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/links/stats": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Stats Link */
        get: operations["stats_link_api_links_stats_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/links/live": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Live Link */
        get: operations["live_link_api_links_live_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Settings */
        get: operations["read_settings_api_settings_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Settings */
        patch: operations["patch_settings_api_settings_patch"];
        trace?: never;
    };
    "/api/settings/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Export Settings
         * @description Return a portable JSON copy without exposing credentials or runtime objects.
         */
        get: operations["export_settings_api_settings_export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/settings/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Import Settings */
        post: operations["import_settings_api_settings_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/settings/reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reset Settings */
        post: operations["reset_settings_api_settings_reset_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/presets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Presets */
        get: operations["read_presets_api_presets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/presets/{slot_key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Patch Preset */
        put: operations["patch_preset_api_presets__slot_key__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/champions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Champions */
        get: operations["champions_api_champions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/catalog/providers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Providers */
        get: operations["providers_api_catalog_providers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/providers/{provider_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Provider Logo */
        get: operations["provider_logo_api_assets_providers__provider_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spells": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Spells */
        get: operations["spells_api_spells_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skins/{champion_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Skins */
        get: operations["skins_api_skins__champion_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Runes */
        get: operations["runes_api_runes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/champions/{champion_id}.png": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Champion Asset */
        get: operations["champion_asset_api_assets_champions__champion_id__png_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/champions/{champion_id}/splash": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Champion Splash Asset */
        get: operations["champion_splash_asset_api_assets_champions__champion_id__splash_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/spells": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Spell Asset */
        get: operations["spell_asset_api_assets_spells_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/runes/perk/{perk_id}.png": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Rune Perk Asset */
        get: operations["rune_perk_asset_api_assets_runes_perk__perk_id__png_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/runes/perk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Rune Perk Asset By Path
         * @description Serve a validated CommunityDragon perk path already returned by the LCU.
         */
        get: operations["rune_perk_asset_by_path_api_assets_runes_perk_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/runes/style": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Rune Style Asset */
        get: operations["rune_style_asset_api_assets_runes_style_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/skins/{champion_id}/{skin_id}.png": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Skin Asset */
        get: operations["skin_asset_api_assets_skins__champion_id___skin_id__png_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/skins/{champion_id}/{skin_id}/splash": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Skin Splash Asset */
        get: operations["skin_splash_asset_api_assets_skins__champion_id___skin_id__splash_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** History */
        get: operations["history_api_history_get"];
        put?: never;
        post?: never;
        /** Clear History */
        delete: operations["clear_history_api_history_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * BootstrapResponse
         * @description Local-only payload required for the first interactive dashboard paint.
         */
        BootstrapResponse: {
            runtime: components["schemas"]["RuntimeSnapshotResponse"];
            settings: components["schemas"]["SettingsResponse"];
            presets: components["schemas"]["PresetsResponse"];
            /** Preset Previews */
            preset_previews?: {
                [key: string]: components["schemas"]["PresetPreview"];
            };
            ban_preview?: components["schemas"]["PresetPreview"] | null;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HealthResponse */
        HealthResponse: {
            /** Ok */
            ok: boolean;
            /** Service */
            service: string;
            /** Version */
            version: string;
            /** Lcu Connected */
            lcu_connected: boolean;
        };
        /** HistoryEntry */
        HistoryEntry: {
            /** Timestamp */
            timestamp: string;
            /** Type */
            type: string;
            /** Level */
            level: string;
            /** Category */
            category: string;
            /** Action */
            action: string;
            /** Message */
            message: string;
            /** Details */
            details: {
                [key: string]: unknown;
            };
        };
        /** HistoryResponse */
        HistoryResponse: {
            /** Items */
            items: components["schemas"]["HistoryEntry"][];
            /** Count */
            count: number;
        };
        /**
         * LiveLinkResponse
         * @description Validated provider link for live-game statistics.
         */
        LiveLinkResponse: {
            /** Available */
            available: boolean;
            /** Site */
            site: string;
            /** Url */
            url: string | null;
            /** Homepage Url */
            homepage_url: string;
            /** Riot Id */
            riot_id: string | null;
            /** Region */
            region: string | null;
            /** Embed Allowed */
            embed_allowed: boolean;
        };
        /** MetadataResponse */
        MetadataResponse: {
            /** Version */
            version: string;
            /** Loaded */
            loaded: boolean;
            /** Champion Count */
            champion_count: number;
            /** Data Dragon Version */
            data_dragon_version?: string | null;
        };
        /**
         * PresetPreview
         * @description Metadata-only preview assembled from already loaded local catalog data.
         */
        PresetPreview: {
            /** Champion Id */
            champion_id?: number | null;
            /**
             * Champion Name
             * @default
             */
            champion_name: string;
            /** Champion Icon Url */
            champion_icon_url?: string | null;
            /** Champion Splash Url */
            champion_splash_url?: string | null;
            /** Spell 1 Url */
            spell_1_url?: string | null;
            /** Spell 2 Url */
            spell_2_url?: string | null;
            /** Skin Name */
            skin_name?: string | null;
            /** Skin Preview Url */
            skin_preview_url?: string | null;
        };
        /**
         * PresetSlotPatch
         * @description Partial update for one of the three champion preset slots.
         */
        PresetSlotPatch: {
            /** Champion */
            champion?: string | null;
            /** Spell 1 */
            spell_1?: string | null;
            /** Spell 2 */
            spell_2?: string | null;
            /** Skin Mode */
            skin_mode?: ("none" | "fixed" | "random") | null;
            /** Skin Id */
            skin_id?: number | null;
            /** Skin Name */
            skin_name?: string | null;
            /** Skin Num */
            skin_num?: number | null;
            /** Random Skin Id */
            random_skin_id?: number | null;
            /** Random Skin Name */
            random_skin_name?: string | null;
            /** Random Skin Num */
            random_skin_num?: number | null;
            /** Random Skin Pool */
            random_skin_pool?: components["schemas"]["SkinReference"][] | null;
            /** Rune Page Id */
            rune_page_id?: number | null;
            /** Rune Page Name */
            rune_page_name?: string | null;
            /** Rune Auto Apply */
            rune_auto_apply?: boolean | null;
            /** Rune Keystone Path */
            rune_keystone_path?: string | null;
            /** Rune Sub Style Icon Path */
            rune_sub_style_icon_path?: string | null;
        };
        /** PresetsResponse */
        PresetsResponse: {
            /** Presets Enabled */
            presets_enabled: boolean;
            /** Selected Ban */
            selected_ban: string;
            /** Slots */
            slots: {
                [key: string]: components["schemas"]["PresetSlotPatch"];
            };
        };
        /** ProviderCatalog */
        ProviderCatalog: {
            /** Stats */
            stats: components["schemas"]["ProviderOption"][];
            /** Live */
            live: components["schemas"]["ProviderOption"][];
            /** Regions */
            regions: components["schemas"]["RegionOption"][];
        };
        /** ProviderOption */
        ProviderOption: {
            /** Id */
            id: string;
            /** Label */
            label: string;
            /** Logo Url */
            logo_url: string;
        };
        /** RegionOption */
        RegionOption: {
            /** Id */
            id: string;
            /** Label */
            label: string;
        };
        /** RuntimeSnapshotResponse */
        RuntimeSnapshotResponse: {
            /** Version */
            version: string;
            /** Connected */
            connected: boolean;
            /** Phase */
            phase: string;
            /** Riot Id */
            riot_id: string | null;
            /** Region */
            region: string;
            /** Queue Id */
            queue_id: number;
            /** Assigned Position */
            assigned_position: string;
            /** Presets Enabled */
            presets_enabled: boolean;
            /** Auto Accept Enabled */
            auto_accept_enabled: boolean;
            /** Auto Pick Enabled */
            auto_pick_enabled: boolean;
            /** Auto Ban Enabled */
            auto_ban_enabled: boolean;
            /** Auto Summoners Enabled */
            auto_summoners_enabled: boolean;
        };
        /**
         * SettingsImport
         * @description Typed current-format settings payload accepted by the import endpoint.
         */
        SettingsImport: {
            /** Auto Accept Enabled */
            auto_accept_enabled?: boolean | null;
            /** Auto Pick Enabled */
            auto_pick_enabled?: boolean | null;
            /** Auto Ban Enabled */
            auto_ban_enabled?: boolean | null;
            /** Auto Summoners Enabled */
            auto_summoners_enabled?: boolean | null;
            /** Presets Enabled */
            presets_enabled?: boolean | null;
            /** Selected Pick 1 */
            selected_pick_1?: string | null;
            /** Selected Pick 2 */
            selected_pick_2?: string | null;
            /** Selected Pick 3 */
            selected_pick_3?: string | null;
            /** Selected Ban */
            selected_ban?: string | null;
            /** Pick Slots */
            pick_slots?: {
                [key: string]: components["schemas"]["PresetSlotPatch"];
            } | null;
            /** Theme */
            theme?: ("darkly" | "flatly") | null;
            /** Summoner Name Auto Detect */
            summoner_name_auto_detect?: boolean | null;
            /** Manual Summoner Name */
            manual_summoner_name?: string | null;
            /** Manual Region */
            manual_region?: ("euw" | "eune" | "na" | "kr" | "jp" | "br" | "lan" | "las" | "oce" | "tr" | "ru") | null;
            /** Preferred Stats Site */
            preferred_stats_site?: ("opgg" | "deeplol" | "dpm" | "leagueofgraphs") | null;
            /** Preferred Hotkey Site */
            preferred_hotkey_site?: ("porofessor" | "deeplol" | "dpm" | "opgg") | null;
            /** Hotkey Toggle Window */
            hotkey_toggle_window?: string | null;
            /** Hotkey Open Site */
            hotkey_open_site?: string | null;
            /** Auto Play Again Enabled */
            auto_play_again_enabled?: boolean | null;
            /** Auto Hide On Connect */
            auto_hide_on_connect?: boolean | null;
            /** Close App On Lol Exit */
            close_app_on_lol_exit?: boolean | null;
            /** Ignored Update Version */
            ignored_update_version?: string | null;
            /** Skin Automation Enabled */
            skin_automation_enabled?: boolean | null;
            /** Window X */
            window_x?: number | null;
            /** Window Y */
            window_y?: number | null;
            /** Window Width */
            window_width?: number | null;
            /** Window Height */
            window_height?: number | null;
            /** Window Maximized */
            window_maximized?: boolean | null;
            /** Config Version */
            config_version?: string | null;
            /** Config Schema Version */
            config_schema_version: number;
            /** Auto Detected Riot Id */
            auto_detected_riot_id?: string | null;
            /** Auto Detected Region */
            auto_detected_region?: string | null;
            /** Auto Detected Platform */
            auto_detected_platform?: string | null;
        };
        /**
         * SettingsPatch
         * @description Allow only settings that the frontend is allowed to edit.
         */
        SettingsPatch: {
            /** Auto Accept Enabled */
            auto_accept_enabled?: boolean | null;
            /** Auto Pick Enabled */
            auto_pick_enabled?: boolean | null;
            /** Auto Ban Enabled */
            auto_ban_enabled?: boolean | null;
            /** Auto Summoners Enabled */
            auto_summoners_enabled?: boolean | null;
            /** Presets Enabled */
            presets_enabled?: boolean | null;
            /** Selected Pick 1 */
            selected_pick_1?: string | null;
            /** Selected Pick 2 */
            selected_pick_2?: string | null;
            /** Selected Pick 3 */
            selected_pick_3?: string | null;
            /** Selected Ban */
            selected_ban?: string | null;
            /** Pick Slots */
            pick_slots?: {
                [key: string]: components["schemas"]["PresetSlotPatch"];
            } | null;
            /** Theme */
            theme?: ("darkly" | "flatly") | null;
            /** Summoner Name Auto Detect */
            summoner_name_auto_detect?: boolean | null;
            /** Manual Summoner Name */
            manual_summoner_name?: string | null;
            /** Manual Region */
            manual_region?: ("euw" | "eune" | "na" | "kr" | "jp" | "br" | "lan" | "las" | "oce" | "tr" | "ru") | null;
            /** Preferred Stats Site */
            preferred_stats_site?: ("opgg" | "deeplol" | "dpm" | "leagueofgraphs") | null;
            /** Preferred Hotkey Site */
            preferred_hotkey_site?: ("porofessor" | "deeplol" | "dpm" | "opgg") | null;
            /** Hotkey Toggle Window */
            hotkey_toggle_window?: string | null;
            /** Hotkey Open Site */
            hotkey_open_site?: string | null;
            /** Auto Play Again Enabled */
            auto_play_again_enabled?: boolean | null;
            /** Auto Hide On Connect */
            auto_hide_on_connect?: boolean | null;
            /** Close App On Lol Exit */
            close_app_on_lol_exit?: boolean | null;
            /** Ignored Update Version */
            ignored_update_version?: string | null;
            /** Skin Automation Enabled */
            skin_automation_enabled?: boolean | null;
            /** Window X */
            window_x?: number | null;
            /** Window Y */
            window_y?: number | null;
            /** Window Width */
            window_width?: number | null;
            /** Window Height */
            window_height?: number | null;
            /** Window Maximized */
            window_maximized?: boolean | null;
        };
        /** SettingsResponse */
        SettingsResponse: {
            /** Config Version */
            config_version: string;
            /** Config Schema Version */
            config_schema_version: number;
            /** Auto Accept Enabled */
            auto_accept_enabled: boolean;
            /** Auto Pick Enabled */
            auto_pick_enabled: boolean;
            /** Auto Ban Enabled */
            auto_ban_enabled: boolean;
            /** Auto Summoners Enabled */
            auto_summoners_enabled: boolean;
            /** Presets Enabled */
            presets_enabled: boolean;
            /** Selected Pick 1 */
            selected_pick_1: string;
            /** Selected Pick 2 */
            selected_pick_2: string;
            /** Selected Pick 3 */
            selected_pick_3: string;
            /** Selected Ban */
            selected_ban: string;
            /** Pick Slots */
            pick_slots: {
                [key: string]: components["schemas"]["PresetSlotPatch"];
            };
            /**
             * Theme
             * @enum {string}
             */
            theme: "darkly" | "flatly";
            /** Summoner Name Auto Detect */
            summoner_name_auto_detect: boolean;
            /** Manual Summoner Name */
            manual_summoner_name: string;
            /** Manual Region */
            manual_region: string;
            /** Auto Detected Riot Id */
            auto_detected_riot_id: string;
            /** Auto Detected Region */
            auto_detected_region: string;
            /** Auto Detected Platform */
            auto_detected_platform: string;
            /** Preferred Stats Site */
            preferred_stats_site: string;
            /** Preferred Hotkey Site */
            preferred_hotkey_site: string;
            /** Hotkey Toggle Window */
            hotkey_toggle_window: string;
            /** Hotkey Open Site */
            hotkey_open_site: string;
            /** Auto Play Again Enabled */
            auto_play_again_enabled: boolean;
            /** Auto Hide On Connect */
            auto_hide_on_connect: boolean;
            /** Close App On Lol Exit */
            close_app_on_lol_exit: boolean;
            /** Ignored Update Version */
            ignored_update_version: string;
            /** Skin Automation Enabled */
            skin_automation_enabled: boolean;
            /** Window X */
            window_x: number;
            /** Window Y */
            window_y: number;
            /** Window Width */
            window_width: number;
            /** Window Height */
            window_height: number;
            /** Window Maximized */
            window_maximized: boolean;
        };
        /** SkinReference */
        SkinReference: {
            /** Skin Id */
            skin_id: number;
            /** Skin Name */
            skin_name: string;
            /** Skin Num */
            skin_num: number;
        };
        /** StatsLinkResponse */
        StatsLinkResponse: {
            /** Available */
            available: boolean;
            /** Site */
            site: string;
            /** Url */
            url: string | null;
            /** Homepage Url */
            homepage_url: string;
            /** Riot Id */
            riot_id: string | null;
            /** Region */
            region: string | null;
            /** Embed Allowed */
            embed_allowed: boolean;
        };
        /** UpdateMetadata */
        UpdateMetadata: {
            /** Version */
            version: string;
            /**
             * Highlights
             * @default
             */
            highlights: string;
            /**
             * Release Url
             * @default
             */
            release_url: string;
            /**
             * Asset Name
             * @default
             */
            asset_name: string;
            /**
             * Asset Url
             * @default
             */
            asset_url: string;
            /**
             * Checksum Name
             * @default
             */
            checksum_name: string;
            /**
             * Checksum Url
             * @default
             */
            checksum_url: string;
        };
        /** UpdatesResponse */
        UpdatesResponse: {
            /** Available */
            available: boolean;
            update: components["schemas"]["UpdateMetadata"] | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    runtime_snapshot_api_runtime_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RuntimeSnapshotResponse"];
                };
            };
        };
    };
    bootstrap_api_bootstrap_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BootstrapResponse"];
                };
            };
        };
    };
    metadata_api_metadata_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MetadataResponse"];
                };
            };
        };
    };
    updates_api_updates_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UpdatesResponse"];
                };
            };
        };
    };
    stats_link_api_links_stats_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatsLinkResponse"];
                };
            };
        };
    };
    live_link_api_links_live_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LiveLinkResponse"];
                };
            };
        };
    };
    read_settings_api_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SettingsResponse"];
                };
            };
        };
    };
    patch_settings_api_settings_patch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SettingsPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SettingsResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_settings_api_settings_export_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    import_settings_api_settings_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SettingsImport"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SettingsResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reset_settings_api_settings_reset_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SettingsResponse"];
                };
            };
        };
    };
    read_presets_api_presets_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PresetsResponse"];
                };
            };
        };
    };
    patch_preset_api_presets__slot_key__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slot_key: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PresetSlotPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PresetsResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    champions_api_champions_get: {
        parameters: {
            query?: {
                q?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    providers_api_catalog_providers_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderCatalog"];
                };
            };
        };
    };
    provider_logo_api_assets_providers__provider_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    spells_api_spells_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    skins_api_skins__champion_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                champion_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    runes_api_runes_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    champion_asset_api_assets_champions__champion_id__png_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                champion_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    champion_splash_asset_api_assets_champions__champion_id__splash_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                champion_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    spell_asset_api_assets_spells_get: {
        parameters: {
            query: {
                name: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    rune_perk_asset_api_assets_runes_perk__perk_id__png_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                perk_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    rune_perk_asset_by_path_api_assets_runes_perk_get: {
        parameters: {
            query: {
                path: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    rune_style_asset_api_assets_runes_style_get: {
        parameters: {
            query: {
                path: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    skin_asset_api_assets_skins__champion_id___skin_id__png_get: {
        parameters: {
            query?: {
                skin_num?: number | null;
            };
            header?: never;
            path: {
                champion_id: number;
                skin_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    skin_splash_asset_api_assets_skins__champion_id___skin_id__splash_get: {
        parameters: {
            query?: {
                skin_num?: number | null;
            };
            header?: never;
            path: {
                champion_id: number;
                skin_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    history_api_history_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HistoryResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    clear_history_api_history_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: boolean;
                    };
                };
            };
        };
    };
}
