/** Ported from tests/test_presentation.py + test_bulk_review.py —
 * the honesty-rule helpers that moved from presentation/ to this file.
 */
import { describe, expect, it } from "vitest";
import {
  displayTitle,
  huf,
  titleGroups,
  evidenceKind,
} from "./labels";

const rec = (id: number, title: string, kind: string) => ({
  id,
  title,
  kind,
});

describe("displayTitle", () => {
  it("strips markdown markers and stray punctuation", () => {
    expect(displayTitle("**Green streets **")).toBe("Green streets");
    expect(displayTitle("  ## Heading:  ")).toBe("Heading");
    expect(displayTitle("1.2. Objective —")).toBe("1.2. Objective");
  });

  it("handles empty input", () => {
    expect(displayTitle("")).toBe("");
    expect(displayTitle(null)).toBe("");
  });
});

describe("titleGroups", () => {
  it("groups identical normalized titles, keeps every record", () => {
    const records = [
      rec(1, "**Green streets **", "objective"),
      rec(2, "Green streets", "objective"),
      rec(3, "Green streets", "target"), // same title, different kind
      rec(4, "Other", "objective"),
    ];
    const groups = titleGroups(records, (r) => r.title, (r) => r.kind);
    expect(groups).toHaveLength(3);
    const main = groups.find((g) => g.length === 2)!;
    expect(main.map((r) => r.id).sort()).toEqual([1, 2]);
    // kind is part of the key — a target never merges with an objective
    expect(groups.flat().map((r) => r.id).sort()).toEqual([1, 2, 3, 4]);
  });

  it("never merges different titles", () => {
    const groups = titleGroups(
      [rec(1, "A", "measure"), rec(2, "B", "measure")],
      (r) => r.title,
      (r) => r.kind,
    );
    expect(groups).toHaveLength(2);
  });
});

describe("huf", () => {
  it("formats with space thousands separator", () => {
    expect(huf(1234567)).toBe("1 234 567 Ft");
    expect(huf(null)).toBe("");
  });
});

describe("evidenceKind", () => {
  it("labels strategy/report URLs differently from project pages", () => {
    expect(evidenceKind("https://x.hu/strategy.pdf", "x")).toBe(
      "Strategy / report",
    );
    expect(evidenceKind("https://x.hu/proj/1", "Street works")).toBe(
      "Project / update",
    );
  });
});
