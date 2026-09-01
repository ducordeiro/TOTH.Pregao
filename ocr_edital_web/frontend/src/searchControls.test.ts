import { describe, expect, it } from "vitest";
import {
  ONLINE_SEARCH_MAX_POLLS,
  ONLINE_SEARCH_POLL_MS,
  SEARCH_PAGE_SIZE,
  shouldDeferOnlinePolling,
  toggleOrderedValue,
} from "./searchControls";

describe("search controls", () => {
  it("keeps the online wait bounded to one minute", () => {
    expect(ONLINE_SEARCH_MAX_POLLS * ONLINE_SEARCH_POLL_MS).toBe(60_000);
  });

  it("requests fifty opportunities per visible page", () => {
    expect(SEARCH_PAGE_SIZE).toBe(50);
  });

  it("defers a timed-out online search when local results remain available", () => {
    expect(shouldDeferOnlinePolling({ results: [], timed_out: true, searching: false }, true)).toBe(true);
    expect(shouldDeferOnlinePolling({ results: [], timed_out: true, searching: true }, true)).toBe(false);
    expect(shouldDeferOnlinePolling({ results: [{} as never], timed_out: true, searching: false }, true)).toBe(false);
    expect(shouldDeferOnlinePolling({ results: [], timed_out: true, searching: false }, false)).toBe(false);
  });

  it("toggles UFs while preserving the official display order", () => {
    const order = ["AC", "AL", "AP", "AM"];
    expect(toggleOrderedValue(["AM"], "AC", order)).toEqual(["AC", "AM"]);
    expect(toggleOrderedValue(["AC", "AM"], "AC", order)).toEqual(["AM"]);
  });
});
