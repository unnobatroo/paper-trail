// @vitest-environment jsdom
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api, type Job } from "./api";
import { keys, useInvalidateDomain, useJobs } from "./hooks";

const job = (id: string, status: Job["status"]): Job => ({
  id, status, kind: "find_evidence", progress: "", result: null,
  error: null, created_at: "2026-10-01T00:00:00Z",
});
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client }, children);
  return { client, wrapper };
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("background job tracking", () => {
  it("waits for every requested job, including an initial response that is still pending", async () => {
    const { client, wrapper } = setup();
    let resolve!: (value: Job) => void;
    vi.spyOn(api, "job").mockImplementation((id) => id === "fast"
      ? Promise.resolve(job(id, "done"))
      : new Promise<Job>((r) => { resolve = r; }));
    const { result } = renderHook(() => useJobs(["fast", "slow"]), { wrapper });
    expect(result.current.settled).toBe(false);
    await waitFor(() => expect(result.current.jobs).toHaveLength(1));
    expect(result.current.settled).toBe(false);
    await act(async () => resolve(job("slow", "running")));
    await waitFor(() => expect(result.current.running).toBe(true));
    expect(result.current.settled).toBe(false);
    act(() => client.setQueryData(keys.job("slow"), job("slow", "done")));
    await waitFor(() => expect(result.current.settled).toBe(true));
    client.clear();
  });
  it("does not mistake a polling error for a finished search and can retry", async () => {
    const { client, wrapper } = setup();
    vi.spyOn(api, "job").mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValue(job("one", "failed"));
    const { result } = renderHook(() => useJobs(["one"]), { wrapper });
    await waitFor(() => expect(result.current.error?.message).toBe("offline"));
    expect(result.current.settled).toBe(false);
    await act(async () => { await result.current.retry(); });
    await waitFor(() => expect(result.current.settled).toBe(true));
    expect(result.current.jobs[0].status).toBe("failed");
    client.clear();
  });
  it("does not finish an empty batch", () => {
    const { client, wrapper } = setup();
    const { result } = renderHook(() => useJobs([]), { wrapper });
    expect(result.current.settled).toBe(false);
    client.clear();
  });
});
it("invalidates hydrated link inspectors along with review lists", async () => {
  const { client, wrapper } = setup();
  client.setQueryData(keys.link(7), { review_status: "unreviewed" });
  const { result } = renderHook(useInvalidateDomain, { wrapper });
  await act(async () => { await result.current(); });
  expect(client.getQueryState(keys.link(7))?.isInvalidated).toBe(true);
  client.clear();
});
