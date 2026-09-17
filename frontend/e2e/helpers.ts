import type { Page } from "@playwright/test";
import { fileURLToPath } from "node:url";

export const blankSlot = {
  champion: "", spell_1: "", spell_2: "", skin_mode: "none", skin_id: 0, skin_name: "", skin_num: 0,
  random_skin_id: 0, random_skin_name: "", random_skin_num: 0, random_skin_pool: [], rune_page_id: 0,
  rune_page_name: "", rune_auto_apply: true, rune_keystone_path: "", rune_sub_style_icon_path: "",
};

export function createState(connected = false, configured = false) {
  const demoAsset = "/assets/app/garen.webp";
  const slot = configured ? { ...blankSlot, champion: "Garen", spell_1: "Flash", spell_2: "Ignite", skin_mode: "fixed", skin_id: 86013, skin_name: "God-King Garen", skin_num: 13 } : { ...blankSlot };
  const slotTwo = configured ? { ...blankSlot, champion: "Lux", spell_1: "Flash", spell_2: "Teleport", skin_mode: "fixed", skin_id: 99010, skin_name: "Battle Academia Lux", skin_num: 10 } : { ...blankSlot };
  const slotThree = configured ? { ...blankSlot, champion: "Ashe", spell_1: "Flash", spell_2: "Heal", skin_mode: "fixed", skin_id: 22013, skin_name: "PROJECT: Ashe", skin_num: 13 } : { ...blankSlot };
  if (configured) Object.assign(slot, { rune_page_id: 7, rune_page_name: "Ma page Top" });
  const pickSlots = { pick_1: slot, pick_2: slotTwo, pick_3: slotThree };
  const settings = {
    config_version: "11.0", config_schema_version: 6, auto_accept_enabled: false, auto_pick_enabled: false,
    auto_ban_enabled: false, auto_summoners_enabled: false, presets_enabled: configured, selected_pick_1: configured ? "Garen" : "",
    selected_pick_2: configured ? "Lux" : "", selected_pick_3: configured ? "Ashe" : "", selected_ban: configured ? "Teemo" : "", pick_slots: pickSlots,
    theme: "darkly", summoner_name_auto_detect: true, manual_summoner_name: "", manual_region: "euw", auto_detected_riot_id: "", auto_detected_region: "", auto_detected_platform: "", preferred_stats_site: "opgg", preferred_hotkey_site: "porofessor", hotkey_toggle_window: "alt+c", hotkey_open_site: "alt+p", auto_play_again_enabled: false, auto_hide_on_connect: true, close_app_on_lol_exit: true, ignored_update_version: "", skin_automation_enabled: true, window_x: 0, window_y: 0, window_width: 1100, window_height: 760, window_maximized: false,
  };
  const runtime = { version: "11.0", connected, phase: connected ? "Lobby" : "None", riot_id: connected ? "Player#EUW" : "", region: connected ? "euw" : "", queue_id: 0, assigned_position: "", presets_enabled: configured, auto_accept_enabled: false, auto_pick_enabled: false, auto_ban_enabled: false, auto_summoners_enabled: false };
  const preview = (id: number, name: string, skinName: string, skinId: number, skinNum: number) => ({ champion_id: id, champion_name: name, champion_icon_url: demoAsset, champion_splash_url: demoAsset, spell_1_url: demoAsset, spell_2_url: demoAsset, skin_name: skinName, skin_preview_url: skinNum > 0 ? "/api/assets/skins/" + id + "/" + skinId + "/splash?skin_num=" + skinNum : null });
  return { settings, runtime, presets: { presets_enabled: configured, selected_ban: settings.selected_ban, slots: settings.pick_slots }, preset_previews: configured ? { pick_1: preview(86, "Garen", "God-King Garen", 86013, 13), pick_2: preview(99, "Lux", "Battle Academia Lux", 99010, 10), pick_3: preview(22, "Ashe", "PROJECT: Ashe", 22013, 13) } : {}, ban_preview: configured ? preview(17, "Teemo", "", 0, 0) : null };
}

export async function mockLocalApi(page: Page, options: { connected?: boolean; configured?: boolean; assignedPosition?: string; phase?: string; historyItems?: unknown[]; rejectPresetActivation?: boolean; randomSkinPreview?: boolean; alternateSkin?: boolean; autoDetect?: boolean; autoDetectedRiotId?: string; manualRiotId?: string; riotId?: string; region?: string; statsLink?: Partial<{ available: boolean; site: string; url: string | null; homepage_url: string; riot_id: string | null; region: string | null; embed_allowed: boolean }>; liveLink?: Partial<{ available: boolean; site: string; url: string | null; homepage_url: string; riot_id: string | null; region: string | null; embed_allowed: boolean }> } = {}) {
  const state = createState(options.connected, options.configured);
  state.runtime.assigned_position = options.assignedPosition ?? "";
  state.runtime.phase = options.phase ?? state.runtime.phase;
  state.runtime.riot_id = options.riotId ?? (options.connected ? "Player#EUW" : "");
  state.runtime.region = options.region ?? (options.connected ? "euw" : "");
  state.settings.summoner_name_auto_detect = options.autoDetect ?? true;
  state.settings.auto_detected_riot_id = options.autoDetectedRiotId ?? (options.connected ? state.runtime.riot_id : "");
  state.settings.auto_detected_region = state.runtime.region;
  state.settings.manual_summoner_name = options.manualRiotId ?? "";
  const statsLink = {
    available: false,
    site: "opgg",
    url: null,
    homepage_url: "https://op.gg/",
    riot_id: null,
    region: null,
    embed_allowed: false,
    ...options.statsLink,
  };
  const liveLink = {
    available: false,
    site: "porofessor",
    url: null,
    homepage_url: "https://porofessor.gg/",
    riot_id: null,
    region: null,
    embed_allowed: false,
    ...options.liveLink,
  };
  if (options.randomSkinPreview) Object.assign(state.presets.slots.pick_1, {
    skin_mode: "random",
    random_skin_id: 86013,
    random_skin_name: "God-King Garen",
    random_skin_num: 13,
    random_skin_pool: [{ skin_id: 86013, skin_name: "God-King Garen", skin_num: 13 }],
  });
  const demoAsset = "/assets/app/garen.webp";
  let historyItems = options.historyItems ?? [];
  await page.addInitScript(() => {
    class QuietWebSocket {
      static CONNECTING = 0;
      static CLOSED = 3;
      static latest: QuietWebSocket | null = null;
      readyState = 1;
      onopen: (() => void) | null = null;
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;
      onmessage: ((event: { data: string }) => void) | null = null;

      constructor() {
        QuietWebSocket.latest = this;
        window.setTimeout(() => this.onopen?.(), 0);
      }

      emit(event: unknown) {
        this.onmessage?.({ data: JSON.stringify(event) });
      }

      close() {
        this.readyState = QuietWebSocket.CLOSED;
        this.onclose?.();
      }
    }
    Object.defineProperty(window, "WebSocket", { configurable: true, value: QuietWebSocket });
    Object.defineProperty(window, "__otpEmitRuntimeEvent", { configurable: true, value: (event: unknown) => QuietWebSocket.latest?.emit(event) });
  });
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith("/api/")) {
      await route.continue();
      return;
    }
    const method = route.request().method();
    let payload: unknown = {};
    if (url.pathname === "/api/bootstrap") payload = state;
    else if (url.pathname === "/api/settings") {
      if (method === "PATCH") {
        const changes = route.request().postDataJSON() as Record<string, unknown>;
        if (options.rejectPresetActivation && changes.presets_enabled === true && !state.settings.selected_pick_1 && !state.settings.selected_pick_2 && !state.settings.selected_pick_3) {
          await route.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify({ detail: "Configure au moins un champion avant d'activer les presets." }) });
          return;
        }
        Object.assign(state.settings, changes);
        if (typeof changes.presets_enabled === "boolean") state.presets.presets_enabled = changes.presets_enabled;
        if (typeof changes.selected_ban === "string") state.presets.selected_ban = changes.selected_ban;
      }
      payload = state.settings;
    } else if (url.pathname === "/api/settings/import" && method === "POST") {
      const changes = route.request().postDataJSON() as Record<string, unknown>;
      if (changes.config_schema_version !== state.settings.config_schema_version) {
        await route.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify({ detail: "Unsupported settings schema" }) });
        return;
      }
      Object.assign(state.settings, changes);
      payload = state.settings;
    } else if (url.pathname === "/api/settings/reset" && method === "POST") {
      state.settings.theme = "darkly";
      payload = state.settings;
    } else if (url.pathname === "/api/runtime") payload = state.runtime;
    else if (url.pathname === "/api/catalog/providers") payload = {
      stats: [
        { id: "opgg", label: "OP.GG", logo_url: "/api/assets/providers/opgg" },
        { id: "deeplol", label: "DeepLOL", logo_url: "/api/assets/providers/deeplol" },
        { id: "dpm", label: "DPM.LOL", logo_url: "/api/assets/providers/dpm" },
        { id: "leagueofgraphs", label: "League of Graphs", logo_url: "/api/assets/providers/leagueofgraphs" },
      ],
      live: [
        { id: "porofessor", label: "Porofessor", logo_url: "/api/assets/providers/porofessor" },
        { id: "deeplol", label: "DeepLOL", logo_url: "/api/assets/providers/deeplol" },
        { id: "dpm", label: "DPM.LOL", logo_url: "/api/assets/providers/dpm" },
        { id: "opgg", label: "OP.GG", logo_url: "/api/assets/providers/opgg" },
      ],
      regions: ["euw", "eune", "na", "kr", "jp", "br", "lan", "las", "oce", "tr", "ru"].map((id) => ({ id, label: id.toUpperCase() })),
    };
    else if (url.pathname === "/api/presets") payload = state.presets;
    else if (url.pathname.startsWith("/api/presets/") && method === "PUT") {
      const key = url.pathname.split("/").pop();
      if (key !== "pick_1" && key !== "pick_2" && key !== "pick_3") {
        await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Unknown preset slot" }) });
        return;
      }
      const changes = route.request().postDataJSON() as Record<string, unknown>;
      Object.assign(state.presets.slots[key], changes);
      if (key === "pick_1" && typeof changes.skin_id === "number") {
        const previews = state.preset_previews as Record<string, { champion_id: number; skin_name: string | null; skin_preview_url: string | null }>;
        const preview = previews[key];
        if (preview) {
          preview.skin_name = String(changes.skin_name ?? "") || null;
          preview.skin_preview_url = Number(changes.skin_num) > 0
            ? `/api/assets/skins/${preview.champion_id}/${changes.skin_id}/splash?skin_num=${changes.skin_num}`
            : null;
        }
      }
      if (typeof changes.champion === "string") {
        const selectedKey = ({ pick_1: "selected_pick_1", pick_2: "selected_pick_2", pick_3: "selected_pick_3" } as const)[key];
        state.settings[selectedKey] = changes.champion;
      }
      payload = state.presets;
    } else if (url.pathname === "/api/champions") {
      const isTeemo = url.searchParams.get("q")?.toLowerCase().includes("teemo");
      payload = { items: [{ id: isTeemo ? 17 : 86, name: isTeemo ? "Teemo" : "Garen", slug: isTeemo ? "Teemo" : "Garen", title: isTeemo ? "L’éclaireur de Bantam" : "La Force de Demacia", tags: ["Fighter"], roles: ["TOP"], icon_url: demoAsset, splash_url: demoAsset }], count: 1 };
    }
    else if (url.pathname === "/api/spells") payload = { items: [{ name: "(None)", icon_url: null }, { name: "Flash", icon_url: demoAsset }, { name: "Ignite", icon_url: demoAsset }] };
    else if (url.pathname.startsWith("/api/skins/")) {
      const catalog = [{ champion_id: 86, champion_name: "Garen", champion_slug: "Garen", skin_id: 86013, skin_num: 13, skin_name: "God-King Garen", splash_url: demoAsset, tile_url: demoAsset, centered_splash_url: demoAsset, uncentered_splash_url: demoAsset }];
      const ownedSkins = [{ skin_id: 86013, skin_num: 13, skin_name: "God-King Garen", preview_url: demoAsset, tile_url: demoAsset, splash_url: demoAsset }];
      if (options.alternateSkin) {
        catalog.push({ champion_id: 86, champion_name: "Garen", champion_slug: "Garen", skin_id: 86014, skin_num: 14, skin_name: "Steel Legion Garen", splash_url: demoAsset, tile_url: demoAsset, centered_splash_url: demoAsset, uncentered_splash_url: demoAsset });
        ownedSkins.push({ skin_id: 86014, skin_num: 14, skin_name: "Steel Legion Garen", preview_url: demoAsset, tile_url: demoAsset, splash_url: demoAsset });
      }
      payload = { champion_id: 86, catalog, owned: { ok: true, owned_skins: ownedSkins, message: "" } };
    }
    else if (url.pathname === "/api/runes") payload = { available: false, pages: [], styles: {} };
    else if (url.pathname === "/api/links/stats") payload = statsLink;
    else if (url.pathname === "/api/links/live") payload = liveLink;
    else if (url.pathname === "/api/updates") payload = { available: false, update: null };
    else if (url.pathname === "/api/history") { if (method === "DELETE") historyItems = []; payload = { items: historyItems, count: historyItems.length }; }
    if (url.pathname === "/api/champions") {
      const catalog = [
        { id: 86, name: "Garen", slug: "Garen", title: "La Force de Demacia", tags: ["Fighter"], roles: ["TOP"], icon_url: demoAsset, splash_url: demoAsset },
        { id: 99, name: "Lux", slug: "Lux", title: "Dame de lumière", tags: ["Mage"], roles: ["MIDDLE"], icon_url: demoAsset, splash_url: demoAsset },
        { id: 22, name: "Ashe", slug: "Ashe", title: "Archère de glace", tags: ["Marksman"], roles: ["BOTTOM"], icon_url: demoAsset, splash_url: demoAsset },
        { id: 17, name: "Teemo", slug: "Teemo", title: "Bandle Scout", tags: ["Marksman"], roles: ["TOP"], icon_url: demoAsset, splash_url: demoAsset },
      ];
      const query = (url.searchParams.get("q") ?? "").toLocaleLowerCase();
      const items = catalog.filter((champion) => !query || champion.name.toLocaleLowerCase().includes(query));
      payload = { items, count: items.length };
    }
    if (url.pathname.startsWith("/api/assets/")) {
      await route.fulfill({ path: fileURLToPath(new URL("../public/assets/app/garen.webp", import.meta.url)) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
  });
  return state;
}
