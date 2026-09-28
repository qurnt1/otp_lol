import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { HistoryPage } from "./HistoryPage";

vi.mock("../../api/client", () => ({
  api: {
    getHistory: vi.fn(),
    clearHistory: vi.fn(),
  },
}));

const historyEntry = {
  timestamp: "2026-09-28T12:00:00Z",
  type: "summoner_spell",
  level: "success",
  category: "summs",
  action: "set_summoners",
  message: "Summoner spells applied",
  details: {},
};

function renderHistory() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><HistoryPage /></QueryClientProvider>);
}

describe("HistoryPage", () => {
  beforeEach(() => {
    vi.mocked(api.getHistory).mockResolvedValue({ items: [historyEntry], count: 1 });
  });

  it("filters summoner spell events and shows a clear failure without allowing duplicate submits", async () => {
    let rejectClear!: (reason: Error) => void;
    vi.mocked(api.clearHistory).mockImplementation(() => new Promise((_, reject) => { rejectClear = reject; }));
    renderHistory();

    fireEvent.click(await screen.findByRole("button", { name: "Sorts" }));
    expect(screen.getByText("Summoner spells applied")).toBeVisible();
    fireEvent.click(screen.getAllByRole("button", { name: "Effacer l’historique" })[0]);

    const dialog = await screen.findByRole("alertdialog");
    const confirm = within(dialog).getByRole("button", { name: "Effacer l’historique" });
    fireEvent.click(confirm);
    await waitFor(() => expect(confirm).toBeDisabled());
    fireEvent.click(confirm);
    expect(api.clearHistory).toHaveBeenCalledTimes(1);

    await act(async () => rejectClear(new Error("disk full")));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Impossible d’effacer l’historique.");
  });
});
