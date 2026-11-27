import { describe, expect, it } from "vitest"

import { firstPage } from "@/lib/rows"
import { candidate, row } from "@/test/fixtures"

describe("firstPage", () => {
  it("is the lowest page of any mention, whichever mention is shown", () => {
    const r = row({ group: [candidate({ id: 1, source_page: 138 }), candidate({ id: 2, source_page: 6 })] })
    expect(firstPage(r)).toBe(6)
  })
})
