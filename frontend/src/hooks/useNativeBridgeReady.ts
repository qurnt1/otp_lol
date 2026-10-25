import { useEffect, useState } from "react";
import { isNativeBridgeExpected, isNativeBridgeReady } from "../domain/external";

export function useNativeBridgeReady(): boolean {
  const [ready, setReady] = useState(isNativeBridgeReady);
  useEffect(() => {
    if (!isNativeBridgeExpected()) {
      setReady(true);
      return;
    }
    const onReady = () => setReady(isNativeBridgeReady());
    window.addEventListener("pywebviewready", onReady);
    if (isNativeBridgeReady()) setReady(true);
    return () => window.removeEventListener("pywebviewready", onReady);
  }, []);
  return ready;
}
