import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"

import { useMentionDecision } from "@/hooks/use-mention-decision"

describe("useMentionDecision", () => {
  it("sends one decision when two are fired at once, even from two places", async () => {
    const posts: string[] = []
    let answer = () => {}
    vi.stubGlobal("fetch", (request: Request) => {
      posts.push(new URL(request.url).pathname)
      // the first request stays on its way until the test lets it answer
      return new Promise<Response>((resolve) => {
        answer = () => resolve(new Response(JSON.stringify({ commitment_id: 1 }), { headers: { "content-type": "application/json" } }))
      })
    })
    const client = new QueryClient()
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
    // the button and the keyboard each hold their own copy of the hook
    const button = renderHook(() => useMentionDecision(), { wrapper })
    const keyboard = renderHook(() => useMentionDecision(), { wrapper })

    act(() => {
      button.result.current.decide(5, "accept")
      keyboard.result.current.decide(5, "reject")
      button.result.current.decide(5, "accept")
    })
    await vi.waitFor(() => expect(posts).toEqual(["/api/candidates/5/accept"]))
    await act(async () => answer())
  })
})
