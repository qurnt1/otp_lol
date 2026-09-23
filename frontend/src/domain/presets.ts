export const presetSlotKeys = ["pick_1", "pick_2", "pick_3"] as const;
export const dashboardActions = [...presetSlotKeys, "ban"] as const;

export type PresetSlotKey = typeof presetSlotKeys[number];
export type DashboardAction = typeof dashboardActions[number];
