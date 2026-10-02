import type { RuntimeEvent } from "../types/api";

type EventHandler = (event: RuntimeEvent) => void;

export function connectRuntimeEvents(onEvent: EventHandler): () => void {
  let socket: WebSocket | null = null;
  let retryTimer: number | undefined;
  let stopped = false;
  let retryAttempt = 0;

  const connect = () => {
    if (stopped) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(`${protocol}//${window.location.host}/api/events`);

    socket.onopen = () => {
      retryAttempt = 0;
    };
    socket.onmessage = (message) => {
      try {
        onEvent(JSON.parse(message.data) as RuntimeEvent);
      } catch {
        // Ignore malformed messages. The next runtime snapshot can recover state.
      }
    };
    socket.onclose = () => {
      socket = null;
      if (stopped) return;
      const delay = Math.min(1000 * 2 ** retryAttempt, 15000);
      retryAttempt += 1;
      retryTimer = window.setTimeout(connect, delay);
    };
  };

  connect();

  return () => {
    stopped = true;
    if (retryTimer !== undefined) window.clearTimeout(retryTimer);
    if (socket?.readyState === WebSocket.CONNECTING) {
      const pendingSocket = socket;
      pendingSocket.onopen = () => pendingSocket.close();
      pendingSocket.onclose = null;
      pendingSocket.onerror = null;
    } else {
      socket?.close();
    }
    socket = null;
  };
}
