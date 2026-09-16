import { afterEach, describe, expect, it, vi } from "vitest";

import { connectRuntimeEvents } from "./events";

class FakeWebSocket {
  static CONNECTING = 0;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  readyState = FakeWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((message: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closeCalls = 0;
  url: string;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  close() {
    this.closeCalls += 1;
    this.readyState = FakeWebSocket.CLOSED;
  }
}

describe("runtime WebSocket client", () => {
  afterEach(() => {
    FakeWebSocket.instances = [];
    vi.unstubAllGlobals();
  });

  it("reconnects with a backoff and stops reconnecting after cleanup", () => {
    const timers = new Map<number, () => void>();
    let nextTimer = 1;
    const windowStub = {
      location: { protocol: "http:", host: "127.0.0.1:5173" },
      setTimeout: (callback: () => void, delay: number) => {
        timers.set(nextTimer, callback);
        expect(delay).toBe(1000);
        return nextTimer++;
      },
      clearTimeout: (id: number) => timers.delete(id),
    };
    vi.stubGlobal("window", windowStub);
    vi.stubGlobal("WebSocket", FakeWebSocket);

    const dispose = connectRuntimeEvents(vi.fn());
    const first = FakeWebSocket.instances[0];
    expect(first.url).toBe("ws://127.0.0.1:5173/api/events");

    first.onclose?.();
    expect(timers.size).toBe(1);
    timers.get(1)?.();
    expect(FakeWebSocket.instances).toHaveLength(2);

    dispose();
    FakeWebSocket.instances[1].onopen?.();
    expect(FakeWebSocket.instances[1].closeCalls).toBe(1);
    expect(timers.size).toBe(0);
  });
});
