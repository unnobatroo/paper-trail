import { describe, expect, it } from "vitest"

import { displayTitle, evidenceKind, goal, huf, pageLink } from "@/lib/labels"
import { parseCode, rowTitle, shown } from "@/lib/rows"
import { candidate, row } from "@/test/fixtures"

describe("displayTitle", () => {
  it("strips Markdown characters and edge punctuation the model leaves in", () => {
    expect(displayTitle("  **– Fák ültetése:** ")).toBe("Fák ültetése")
    expect(displayTitle(null)).toBe("")
  })
})

describe("goal", () => {
  it("is a dash when nothing is known", () => {
    expect(goal({})).toBe("–")
  })
  it("joins target and deadline", () => {
    expect(goal({ target_value: 100, unit: "fa", deadline_year: 2027 })).toBe("100 fa by 2027")
    expect(goal({ deadline_year: 2030 })).toBe("2030")
    expect(goal({ target_value: 40, unit: "%", timeframe: "2030-ig" })).toBe("40 % by 2030-ig")
  })
})

describe("pageLink", () => {
  it("opens the PDF at the page when the document has a URL", () => {
    expect(pageLink("https://x.org/s.pdf#old", 7)).toEqual({ text: "Strategy · page 7", href: "https://x.org/s.pdf#page=7" })
    expect(pageLink(undefined, 7)).toEqual({ text: "Source · page 7" })
  })
})

describe("huf and evidenceKind", () => {
  it("groups thousands with spaces", () => {
    expect(huf(2000000)).toBe("2 000 000 Ft")
    expect(huf(null)).toBe("")
  })
  it("tells planning documents from project pages", () => {
    expect(evidenceKind("https://x.hu/klimastrategia.pdf", "")).toBe("Strategy / report")
    expect(evidenceKind("https://x.hu/fasor", "Utcafásítás")).toBe("Project / update")
  })
})

describe("rows", () => {
  it("shows the picked mention, else the first open one, else the first", () => {
    const r = row({ group: [candidate({ id: 1, review_status: "accepted" }), candidate({ id: 2 })] })
    expect(shown(r).id).toBe(2)
    expect(shown(r, 1).id).toBe(1)
    expect(shown(r, 99).id).toBe(2)
  })

  it("puts the English reading aid first only when asked", () => {
    const note = { title_en: "Planting trees" } as never
    const r = row({ group: [candidate({ note })] })
    expect(rowTitle(r, true)).toBe("Planting trees · Fák ültetése")
    expect(rowTitle(r, false)).toBe("Fák ültetése")
  })

  it("reads a printed code into its letters and depth", () => {
    expect(parseCode("M1.2.1")).toEqual({ letters: "M", depth: 3 })
    expect(parseCode("Sz1")).toEqual({ letters: "Sz", depth: 1 })
    expect(parseCode("1.01")).toBeNull()
    expect(parseCode(null)).toBeNull()
  })
})
