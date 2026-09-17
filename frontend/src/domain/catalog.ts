import type { ProviderCatalog, RegionOption } from "../types/api";

const defaultRegions: RegionOption[] = ["euw", "eune", "na", "kr", "jp", "br", "lan", "las", "oce", "tr", "ru"]
  .map((id) => ({ id, label: id.toUpperCase() }));

export function regionOptionsOrFallback(catalog: ProviderCatalog | undefined): RegionOption[] {
  return catalog?.regions.length ? catalog.regions : defaultRegions;
}
