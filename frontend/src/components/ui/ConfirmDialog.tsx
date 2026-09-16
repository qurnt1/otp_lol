import type { ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";

import { fr } from "../../content/fr";

export function ConfirmDialog({ open, title, description, confirmLabel, onCancel, onConfirm, children }: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => void;
  children?: ReactNode;
}) {
  return <Dialog.Root open={open} onOpenChange={(nextOpen) => { if (!nextOpen) onCancel(); }}>
    <Dialog.Portal>
      <Dialog.Overlay className="dialog-overlay" />
      <Dialog.Content className="confirm-dialog" role="alertdialog" aria-describedby="confirm-dialog-description">
        <div className="drawer-head"><div><Dialog.Title>{title}</Dialog.Title><Dialog.Description id="confirm-dialog-description">{description}</Dialog.Description></div><Dialog.Close asChild><button className="icon-button" type="button" aria-label={fr.common.close}><X size={16} aria-hidden="true" /></button></Dialog.Close></div>
        {children}
        <div className="confirm-actions"><button className="button" type="button" onClick={onCancel}>{fr.common.cancel}</button><button className="button button-danger" type="button" onClick={onConfirm}>{confirmLabel}</button></div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
