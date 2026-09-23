import { fr } from "../../content/fr";
import type { Champion, Skin, SkinReference } from "../../types/api";

export const roleFilters = [
  { id: "all", label: fr.presets.roleAll, role: "GLOBAL" },
  { id: "top", label: fr.presets.roleTop, role: "TOP" },
  { id: "jungle", label: fr.presets.roleJungle, role: "JUNGLE" },
  { id: "mid", label: fr.presets.roleMid, role: "MIDDLE" },
  { id: "adc", label: fr.presets.roleAdc, role: "BOTTOM" },
  { id: "support", label: fr.presets.roleSupport, role: "UTILITY" },
] as const;

export type RoleFilterId = typeof roleFilters[number]["id"];

const TAG_ROLE_FALLBACK: Record<string, string[]> = {
  marksman: ["BOTTOM"], support: ["UTILITY"], mage: ["MIDDLE", "UTILITY"],
  assassin: ["MIDDLE", "JUNGLE"], fighter: ["TOP", "JUNGLE"], tank: ["TOP", "JUNGLE", "UTILITY"],
};

function championRoles(champion: Champion): string[] {
  if (champion.roles?.length) return champion.roles.map((role) => role.toUpperCase());
  return champion.tags.flatMap((tag) => TAG_ROLE_FALLBACK[tag.toLowerCase()] ?? []);
}

export function filterChampions(champions: Champion[], query: string, role: RoleFilterId): Champion[] {
  const needle = query.trim().toLocaleLowerCase();
  const roleValue = roleFilters.find((item) => item.id === role)?.role ?? "GLOBAL";
  return champions.filter((champion) => {
    const matchesQuery = !needle || `${champion.name} ${champion.slug}`.toLocaleLowerCase().includes(needle);
    const matchesRole = roleValue === "GLOBAL" || championRoles(champion).includes(roleValue);
    return matchesQuery && matchesRole;
  });
}

function referenceFromSkin(skin: Skin): SkinReference {
  return { skin_id: skin.skin_id, skin_name: skin.skin_name, skin_num: skin.skin_num };
}

export function updateSkinPool(pool: SkinReference[], catalog: Skin[], skin: Skin, checked: boolean): SkinReference[] {
  const catalogById = new Map(catalog.map((item) => [item.skin_id, referenceFromSkin(item)]));
  const next = new Map(pool.map((item) => [item.skin_id, item]));
  if (checked) next.set(skin.skin_id, referenceFromSkin(skin));
  else next.delete(skin.skin_id);
  return [...next.values()].map((item) => catalogById.get(item.skin_id) ?? item);
}

export function selectAllVisibleSkins(pool: SkinReference[], visibleSkins: Skin[]): SkinReference[] {
  const next = new Map(pool.map((item) => [item.skin_id, item]));
  for (const skin of visibleSkins) next.set(skin.skin_id, referenceFromSkin(skin));
  return [...next.values()];
}
