import type { SearchResponse } from "./types";

export const ONLINE_SEARCH_MAX_POLLS = 60;
export const ONLINE_SEARCH_POLL_MS = 1_000;
export const SEARCH_PAGE_SIZE = 50;

export function shouldDeferOnlinePolling(
  payload: Pick<SearchResponse, "results" | "rate_limited" | "searching" | "timed_out">,
  localAvailable: boolean,
) {
  return localAvailable
    && payload.searching === false
    && !payload.results?.length
    && Boolean(payload.timed_out || payload.rate_limited);
}

export function toggleOrderedValue(current: string[], value: string, order: string[]) {
  const next = new Set(current);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return order.filter((candidate) => next.has(candidate));
}
