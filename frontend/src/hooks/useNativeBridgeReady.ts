import { useEffect, useState } from "react";

type NativeWindow = Window & {
  __otpDesktopMode?: boolean;
  __otpNativeBridgeReady?: boolean;
  pywebview?: { api?: unknown };
};

function isDesktopMode(): boolean {
  if (typeof window === "undefined") return false;
  const current = window as NativeWindow;
  return Boolean(current.__otpDesktopMode || new URLSearchParams(window.location.search).get("desktop") === "1");
}

function readReady(): boolean {
  if (typeof window === "undefined") return false;
  const current = window as NativeWindow;
  if (!isDesktopMode() && !("pywebview" in window)) return true;
  return Boolean(current.__otpNativeBridgeReady || current.pywebview?.api);
}

export function useNativeBridgeReady(): boolean {
  const [ready, setReady] = useState(readReady);
  useEffect(() => {
    if (!isDesktopMode() && !("pywebview" in window)) {
      setReady(true);
      return;
    }
    const onReady = () => {
      (window as NativeWindow).__otpNativeBridgeReady = true;
      setReady(true);
    };
    window.addEventListener("pywebviewready", onReady);
    if ((window as NativeWindow).pywebview?.api) setReady(true);
    return () => window.removeEventListener("pywebviewready", onReady);
  }, []);
  return ready;
}
