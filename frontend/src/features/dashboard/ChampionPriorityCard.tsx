import { CircleOff, Moon, Swords } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties, type DragEvent as ReactDragEvent, type KeyboardEvent as ReactKeyboardEvent, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent, type Ref } from "react";

import { runeAssetUrl, safeImageUrl } from "../../domain/assets";
import { cn } from "../../lib/cn";
import type { Champion, PresetPreview, PresetSlot, SummonerSpell } from "../../types/api";
import type { PresetSlotKey } from "../../domain/presets";
import { AssetImage } from "../../components/game/AssetImage";
import { fr } from "../../content/fr";
import { routeToHash } from "../../app/routes";

interface ChampionPriorityCardProps {
  slotKey: PresetSlotKey;
  slot: PresetSlot | undefined;
  index: number;
  spells: SummonerSpell[];
  preview?: PresetPreview;
  champion?: Champion;
  isOpen?: boolean;
  triggerRef?: Ref<HTMLAnchorElement>;
  reorderDisabled?: boolean;
  isDragging?: boolean;
  isDropTarget?: boolean;
  previewOffset?: { x: number; y: number };
  onMove?: (slotKey: PresetSlotKey, delta: -1 | 1) => void;
  onDragStart?: (slotKey: PresetSlotKey) => void;
  onDragTarget?: (slotKey: PresetSlotKey | null) => void;
  onDragEnd?: () => void;
  onDragCancel?: () => void;
  onDrop?: (source: PresetSlotKey, target: PresetSlotKey) => void;
}

interface PointerSession {
  pointerId: number;
  originX: number;
  originY: number;
  timer: number;
  armed: boolean;
  dragging: boolean;
  targetSlot: PresetSlotKey | null;
  element: HTMLElement;
}

const longPressDelayMs = 240;
const pointerMoveThreshold = 7;

export function ChampionPriorityCard({
  slotKey,
  slot,
  index,
  spells,
  preview,
  champion,
  isOpen = false,
  triggerRef,
  reorderDisabled = false,
  isDragging = false,
  isDropTarget = false,
  previewOffset,
  onMove,
  onDragStart,
  onDragTarget,
  onDragEnd,
  onDragCancel,
  onDrop,
}: ChampionPriorityCardProps) {
  const [isPressArmed, setIsPressArmed] = useState(false);
  const pointerSession = useRef<PointerSession | null>(null);
  const suppressClick = useRef(false);
  const reorderDisabledRef = useRef(reorderDisabled);
  const callbacks = useRef({ onMove, onDragStart, onDragTarget, onDragEnd, onDragCancel, onDrop });
  reorderDisabledRef.current = reorderDisabled;
  callbacks.current = { onMove, onDragStart, onDragTarget, onDragEnd, onDragCancel, onDrop };

  useEffect(() => {
    const findTarget = (x: number, y: number): PresetSlotKey | null => {
      const value = document.elementFromPoint(x, y)
        ?.closest<HTMLElement>("[data-priority-slot]")
        ?.dataset.prioritySlot;
      return value === "pick_1" || value === "pick_2" || value === "pick_3" ? value : null;
    };

    const clearSession = (session: PointerSession, preserveDragOffset = false) => {
      window.clearTimeout(session.timer);
      if (!preserveDragOffset) {
        session.element.style.removeProperty("--drag-x");
        session.element.style.removeProperty("--drag-y");
      }
      pointerSession.current = null;
      setIsPressArmed(false);
    };

    const isInsideGrid = (x: number, y: number, element: HTMLElement) => {
      const rect = element.closest(".priority-grid")?.getBoundingClientRect();
      return Boolean(rect && x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom);
    };

    const handlePointerMove = (event: PointerEvent) => {
      const session = pointerSession.current;
      if (!session || event.pointerId !== session.pointerId) return;

      const distance = Math.hypot(event.clientX - session.originX, event.clientY - session.originY);
      if (!session.armed) {
        if (distance > pointerMoveThreshold) clearSession(session);
        return;
      }

      if (!session.dragging) {
        if (distance <= pointerMoveThreshold || reorderDisabledRef.current) return;
        session.dragging = true;
        session.element.style.setProperty("--drag-x", `${event.clientX - session.originX}px`);
        session.element.style.setProperty("--drag-y", `${event.clientY - session.originY}px`);
        setIsPressArmed(false);
        callbacks.current.onDragStart?.(slotKey);
      }

      if (session.dragging) {
        event.preventDefault();
        session.element.style.setProperty("--drag-x", `${event.clientX - session.originX}px`);
        session.element.style.setProperty("--drag-y", `${event.clientY - session.originY}px`);
        const target = findTarget(event.clientX, event.clientY);
        if (target) session.targetSlot = target;
        else if (!isInsideGrid(event.clientX, event.clientY, session.element)) session.targetSlot = null;
        callbacks.current.onDragTarget?.(session.targetSlot);
      }
    };

    const handlePointerUp = (event: PointerEvent) => {
      const session = pointerSession.current;
      if (!session || event.pointerId !== session.pointerId) return;
      if (session.dragging) {
        event.preventDefault();
        const currentTarget = findTarget(event.clientX, event.clientY);
        if (currentTarget) session.targetSlot = currentTarget;
        else if (!isInsideGrid(event.clientX, event.clientY, session.element)) session.targetSlot = null;
        const target = session.targetSlot;
        const commitsReorder = Boolean(target && target !== slotKey);
        suppressClick.current = true;
        if (commitsReorder && target) callbacks.current.onDrop?.(slotKey, target);
        else callbacks.current.onDragCancel?.();
        callbacks.current.onDragTarget?.(null);
        callbacks.current.onDragEnd?.();
        window.setTimeout(() => { suppressClick.current = false; }, 0);
        clearSession(session, commitsReorder);
        if (commitsReorder) {
          window.requestAnimationFrame(() => {
            session.element.style.removeProperty("--drag-x");
            session.element.style.removeProperty("--drag-y");
          });
        }
        return;
      }

      clearSession(session);
    };

    const handlePointerCancel = (event: PointerEvent) => {
      const session = pointerSession.current;
      if (!session || event.pointerId !== session.pointerId) return;
      if (session.dragging) {
        callbacks.current.onDragCancel?.();
        callbacks.current.onDragTarget?.(null);
        callbacks.current.onDragEnd?.();
      }
      clearSession(session);
    };

    window.addEventListener("pointermove", handlePointerMove, { passive: false });
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerCancel);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerCancel);
      const session = pointerSession.current;
      if (session) window.clearTimeout(session.timer);
    };
  }, [slotKey]);

  const championName = slot?.champion?.trim() ?? "";
  const skinMode = slot?.skin_mode ?? "none";
  const skinLabel = skinMode === "fixed" ? preview?.skin_name || fr.presets.skinFixed : skinMode === "random" ? fr.presets.skinRandom : fr.presets.skinNone;
  const championSubtitle = championName ? champion?.title : "À configurer";
  const primarySpell = spells.find((spell) => spell.name === slot?.spell_1);
  const secondarySpell = spells.find((spell) => spell.name === slot?.spell_2);
  const runeKeystoneId = slot?.rune_keystone_id ?? 0;
  const runeIcon = runeKeystoneId > 0
    ? `/api/assets/runes/perk/${runeKeystoneId}.png`
    : runeAssetUrl(slot?.rune_keystone_path, "perk");
  const subRuneIcon = runeAssetUrl(slot?.rune_sub_style_icon_path, "style");
  const championIconUrl = safeImageUrl(preview?.champion_icon_url) ?? safeImageUrl(champion?.icon_url);
  const splashUrl = safeImageUrl(skinMode === "none" ? null : preview?.skin_preview_url)
    ?? safeImageUrl(preview?.champion_splash_url)
    ?? safeImageUrl(champion?.splash_url);

  const handlePointerDown = (event: ReactPointerEvent<HTMLElement>) => {
    if (reorderDisabled || !event.isPrimary || event.button !== 0) return;
    if ((event.target as Element).closest("button, input, select, textarea, [data-no-reorder]")) return;

    const element = event.currentTarget;
    const session: PointerSession = {
      pointerId: event.pointerId,
      originX: event.clientX,
      originY: event.clientY,
      timer: 0,
      armed: false,
      dragging: false,
      targetSlot: null,
      element,
    };
    session.timer = window.setTimeout(() => {
      if (pointerSession.current !== session || reorderDisabledRef.current) return;
      session.armed = true;
      setIsPressArmed(true);
    }, longPressDelayMs);
    pointerSession.current = session;
  };

  const handleClickCapture = (event: ReactMouseEvent<HTMLElement>) => {
    if (!suppressClick.current) return;
    suppressClick.current = false;
    event.preventDefault();
    event.stopPropagation();
  };

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLAnchorElement>) => {
    if (reorderDisabled || !event.altKey) return;
    if (event.key === "ArrowUp") {
      event.preventDefault();
      onMove?.(slotKey, -1);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      onMove?.(slotKey, 1);
    }
  };

  const handleNativeDragStart = (event: ReactDragEvent<HTMLElement>) => {
    event.preventDefault();
  };

  const cardStyle: CSSProperties | undefined = previewOffset ? {
    "--preview-x": `${previewOffset.x}px`,
    "--preview-y": `${previewOffset.y}px`,
  } as CSSProperties : undefined;

  return <article
    className={cn("priority-card", !championName && "is-empty", isDragging && "is-dragging", isDropTarget && "is-drop-target", previewOffset && "is-preview-shifted", isPressArmed && "is-press-armed")}
    data-priority-slot={slotKey}
    style={cardStyle}
    onPointerDown={handlePointerDown}
    onClickCapture={handleClickCapture}
    onDragStart={handleNativeDragStart}
  >
    <a
      ref={triggerRef}
      className="priority-card-link"
      href={routeToHash({ page: "dashboard", action: slotKey })}
      aria-haspopup="dialog"
      aria-expanded={isOpen}
      aria-disabled={reorderDisabled}
      aria-label={`${championName ? `Modifier ${championName}` : "Configurer un champion"}, preset ${index + 1}`}
      aria-describedby={`priority-card-help-${slotKey}`}
      aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown"
      draggable={false}
      onClick={(event) => { if (reorderDisabled) event.preventDefault(); }}
      onKeyDown={handleKeyDown}
    >
      <span id={`priority-card-help-${slotKey}`} className="sr-only">{fr.dashboard.priorityCardAccessibleHint}</span>
      <div className="priority-art">
        {splashUrl && <AssetImage src={splashUrl} alt="" width="640" height="340" loading={index === 0 ? "eager" : "lazy"} draggable={false} />}
        <span className="priority-shade" aria-hidden="true" />
        <span className="priority-number">0{index + 1}</span>
        <span className="priority-caption"><h3>{championName || "Configurer un champion"}</h3>{championSubtitle && <small>{championSubtitle}</small>}</span>
        {!championName && <span className="priority-placeholder"><Swords size={26} aria-hidden="true" /></span>}
      </div>
      <div className="priority-details">
        <div className="asset-row summoner-row" aria-label="Sorts d’invocateur">
          <span className="asset-pair">
            <AssetImage src={safeImageUrl(preview?.spell_1_url ?? primarySpell?.icon_url) ?? undefined} alt={slot?.spell_1 || "Sort 1"} title={slot?.spell_1 || "Sort 1"} width="30" height="30" draggable={false} fallback="S1" />
            <AssetImage src={safeImageUrl(preview?.spell_2_url ?? secondarySpell?.icon_url) ?? undefined} alt={slot?.spell_2 || "Sort 2"} title={slot?.spell_2 || "Sort 2"} width="30" height="30" draggable={false} fallback="S2" />
          </span>
        </div>
        <div className="asset-row rune-row" aria-label="Runes">
          <span className="asset-pair">
            <AssetImage className="rune-asset" src={runeIcon ?? undefined} alt={slot?.rune_page_name || fr.presets.runeNoneHint} title={slot?.rune_page_name || fr.presets.runeNoneHint} width="30" height="30" loading="lazy" draggable={false} fallback={<CircleOff size={15} aria-hidden="true" />} />
            {subRuneIcon && <AssetImage className="rune-asset" src={subRuneIcon} alt="Rune secondaire" title="Rune secondaire" width="22" height="22" loading="lazy" draggable={false} fallback="" />}
          </span>
          <span className="rune-name" title={slot?.rune_page_name || fr.presets.runeNoneHint}>{slot?.rune_page_name || fr.presets.runeNoneHint}</span>
        </div>
        <div className="skin-preview">
          <AssetImage src={championIconUrl ?? undefined} alt="" width="34" height="34" loading="lazy" draggable={false} fallback={<Moon size={15} aria-hidden="true" />} />
          <span><small>SKIN</small><strong>{skinLabel}</strong></span>
        </div>
      </div>
    </a>
  </article>;
}
