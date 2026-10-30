// @vitest-environment jsdom
// error mapping + review-key plumbing, where silent wrongness hangs the ui or skips a gate
import {afterEach, describe, expect, it, vi} from "vitest";
import {api, getReviewKey, setReviewKey} from "./api";

const okJson = (body: unknown = {}) =>
    new Response(JSON.stringify(body), {status: 200});

describe("api client", () => {
    afterEach(() => {
        vi.unstubAllGlobals();
        localStorage.clear();
    });

    it("maps HTTP errors to ApiError with the server's detail", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn(async () =>
                new Response(JSON.stringify({detail: "unknown link 9"}), {
                    status: 404,
                }),
            ),
        );
        await expect(api.documents()).rejects.toMatchObject({
            name: "ApiError",
            status: 404,
            message: "unknown link 9",
        });
    });

    it("turns a timeout into a wake-up message instead of a spinner", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn(async () => {
                throw new DOMException("timed out", "TimeoutError");
            }),
        );
        await expect(api.meta()).rejects.toMatchObject({
            name: "ApiError",
            status: 0,
            message: expect.stringContaining("waking up"),
        });
    });

    it("turns a network failure into a reachability message", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn(async () => {
                throw new TypeError("fetch failed");
            }),
        );
        await expect(api.meta()).rejects.toMatchObject({
            name: "ApiError",
            status: 0,
            message: expect.stringContaining("Cannot reach"),
        });
    });

    it("sends X-Review-Key on writes once a key is stored", async () => {
        setReviewKey("sekret");
        expect(getReviewKey()).toBe("sekret");
        const fetchMock = vi.fn<typeof fetch>(async () => okJson({ok: true}));
        vi.stubGlobal("fetch", fetchMock);
        await api.rejectCandidate(1);
        expect(fetchMock.mock.calls[0][1]?.headers).toMatchObject({
            "x-review-key": "sekret",
        });
    });

    it("keeps reads header-free so they skip the CORS preflight", async () => {
        setReviewKey("sekret");
        const fetchMock = vi.fn<typeof fetch>(async () => okJson([]));
        vi.stubGlobal("fetch", fetchMock);
        await api.documents();
        expect(fetchMock.mock.calls[0][1]?.headers).toEqual({});
        setReviewKey("");
    });

    it("flattens FastAPI 422 details into readable text", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn<typeof fetch>(async () =>
                new Response(
                    JSON.stringify({detail: [{loc: ["body", "texts"], msg: "too long"}]}),
                    {status: 422},
                ),
            ),
        );
        await expect(api.documents()).rejects.toMatchObject({
            status: 422,
            message: "texts: too long",
        });
    });

    it("omits the header with no key, and after clearing", async () => {
        const fetchMock = vi.fn<typeof fetch>(async () => okJson([]));
        vi.stubGlobal("fetch", fetchMock);
        await api.documents();
        expect(fetchMock.mock.calls[0][1]?.headers).not.toHaveProperty(
            "x-review-key",
        );
        setReviewKey("k");
        setReviewKey("");
        expect(getReviewKey()).toBe("");
    });
});
