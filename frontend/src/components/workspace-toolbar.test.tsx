import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { WorkspaceToolbar } from "@/components/workspace-toolbar"
import { PrefsProvider } from "@/lib/prefs"

function renderToolbar(kind = "all", onKind = vi.fn()) {
  render(
    <PrefsProvider>
      <WorkspaceToolbar counts={{ objective: 3, measure: 2 }} kind={kind} onKind={onKind} />
    </PrefsProvider>,
  )
  return onKind
}

describe("WorkspaceToolbar", () => {
  beforeEach(() => localStorage.clear())

  it("offers each kind that has rows, with its count, and the total", () => {
    renderToolbar()
    expect(screen.getByRole("button", { name: "All 5" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Objectives 3" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Measures 2" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Targets/ })).not.toBeInTheDocument()
  })

  it("filters by the clicked kind, and clicking the active one goes back to all", async () => {
    const onKind = renderToolbar()
    await userEvent.click(screen.getByRole("button", { name: "Measures 2" }))
    expect(onKind).toHaveBeenLastCalledWith("measure")
    renderToolbar("measure", onKind)
    await userEvent.click(screen.getAllByRole("button", { name: "Measures 2" })[1])
    expect(onKind).toHaveBeenLastCalledWith("all")
  })

  it("remembers the row density in this browser", async () => {
    renderToolbar()
    await userEvent.click(screen.getByRole("button", { name: "Compact rows" }))
    expect(localStorage.getItem("paper-trail.density")).toBe("compact")
  })
})
