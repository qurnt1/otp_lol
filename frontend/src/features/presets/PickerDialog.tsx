import type { ReactNode, RefObject } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";

import { fr } from "../../content/fr";

export type Picker = { kind: "champion" | "skin" | "runes" | "ban"; slot?: "pick_1" | "pick_2" | "pick_3" } | null;

export function PickerDialog({ picker, onClose, returnFocusRef, children }: { picker: Picker; onClose: () => void; returnFocusRef?: RefObject<HTMLButtonElement | null>; children: ReactNode }) {
  const title = picker?.kind === "champion" ? fr.presets.selectChampion : picker?.kind === "ban" ? fr.presets.ban : picker?.kind === "skin" ? fr.presets.skinGallery : fr.presets.runes;
  return <Dialog.Root open={Boolean(picker)} onOpenChange={(open) => { if (!open) onClose(); }}><Dialog.Portal><Dialog.Overlay className="drawer picker-drawer"><Dialog.Content className="drawer-card" onOpenAutoFocus={(event) => {
    if (picker?.kind !== "champion" && picker?.kind !== "ban") return;
    event.preventDefault();
    window.requestAnimationFrame(() => document.getElementById("champion-search")?.focus());
  }} onCloseAutoFocus={(event) => { if (!returnFocusRef) return; event.preventDefault(); window.requestAnimationFrame(() => returnFocusRef.current?.focus()); }}><div className="drawer-head"><div><Dialog.Title>{title}</Dialog.Title><Dialog.Description>{fr.presets.pickerDescription}</Dialog.Description></div><Dialog.Close asChild><button className="icon-button" type="button" aria-label={fr.common.close}><X size={16} aria-hidden="true" /></button></Dialog.Close></div>{children}</Dialog.Content></Dialog.Overlay></Dialog.Portal></Dialog.Root>;
}
