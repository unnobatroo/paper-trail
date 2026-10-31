"""how much graders agree on evidence labels: people vs people vs the llm judge

  uv run python scripts/ml/label_agreement.py anna.txt bence.txt \\
    --judge data/eval/evidence-qrels-judge.jsonl --out data/eval/evidence-qrels-human.jsonl

grader files are filled-in annotation sheets: the .docx grading sheets (an "ID: q / d" line,
then the number in the grade box) or text with "=== n. <query> / <doc> ===" blocks and a
"grade: N" (or "you: N") line. prints exact/binary agreement and cohen's kappa per pair of
graders, binary = grade >= 2 (counts as evidence). --out writes the human grades as qrels,
the median where several people graded the same pair, later --qrels files override the judge
"""
import argparse
import json
import re
import statistics
import zipfile
from itertools import combinations
from pathlib import Path

_BLOCK = re.compile(r"^=== \d+\. (\S+) / (\S+) ===$")
_GRADE = re.compile(r"^(?:grade|you):\s*([0-3])\b")
_DOCX_ID = re.compile(r"ID: (\S+) / (\S+)$")
_DOCX_GRADE = ("Grade (0–3)", "Pontszám (0–3)")
_DOCX_HINTS = ("one number: 0, 1, 2 or 3", "egy szám: 0, 1, 2 vagy 3")


def _docx_lines(path: Path) -> list[str]:
    """word paragraphs -> the text sheet format, the number after the grade label"""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode()
    paras = ["".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", p)).strip()
             for p in xml.split("</w:p>")]
    paras = [p for p in paras if p and p not in _DOCX_HINTS]
    out = []
    for i, text in enumerate(paras):
        if m := _DOCX_ID.search(text):
            out.append(f"=== 0. {m.group(1)} / {m.group(2)} ===")
        elif text in _DOCX_GRADE and i + 1 < len(paras):
            out.append(f"grade: {paras[i + 1]}")
    return out


def read_sheet(path: Path) -> dict[tuple[str, str], int]:
    grades, pair = {}, None
    lines = _docx_lines(path) if path.suffix == ".docx" else path.read_text().splitlines()
    for line in lines:
        if m := _BLOCK.match(line.strip()):
            pair = m.groups()
        elif pair and (m := _GRADE.match(line.strip())):
            grades[pair] = int(m.group(1))
            pair = None
    return grades


def read_qrels(path: Path) -> dict[tuple[str, str], int]:
    rows = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {(r["query"], r["doc"]): int(r["grade"]) for r in rows}


def kappa(a: list[int], b: list[int]) -> float | None:
    """cohen's kappa, chance-corrected agreement. None when there's nothing to correct"""
    labels = sorted(set(a) | set(b))
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    expected = sum((a.count(lab) / n) * (b.count(lab) / n) for lab in labels)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def compare(x: dict, y: dict) -> dict | None:
    shared = sorted(set(x) & set(y))
    if not shared:
        return None
    a, b = [x[p] for p in shared], [y[p] for p in shared]
    ab, bb = [int(v >= 2) for v in a], [int(v >= 2) for v in b]
    k_bin, k_all = kappa(ab, bb), kappa(a, b)
    return {"pairs": len(shared),
            "exact": round(sum(p == q for p, q in zip(a, b, strict=True)) / len(a), 3),
            "binary": round(sum(p == q for p, q in zip(ab, bb, strict=True)) / len(a), 3),
            "kappa_binary": None if k_bin is None else round(k_bin, 3),
            "kappa_4way": None if k_all is None else round(k_all, 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sheets", type=Path, nargs="+")
    parser.add_argument("--judge", type=Path, help="llm judge qrels to compare against")
    parser.add_argument("--out", type=Path, help="write the human grades as qrels")
    args = parser.parse_args()
    graders = {p.stem: read_sheet(p) for p in args.sheets}
    for name, grades in graders.items():
        print(f"{name}: {len(grades)} graded")
    if args.judge:
        graders["judge"] = read_qrels(args.judge)
    for (na, a), (nb, b) in combinations(graders.items(), 2):
        print(f"{na} vs {nb}: {compare(a, b)}")
    if args.out:
        human: dict[tuple[str, str], list[int]] = {}
        for name, grades in graders.items():
            if name != "judge":
                for pair, grade in grades.items():
                    human.setdefault(pair, []).append(grade)
        args.out.write_text("".join(
            json.dumps({"query": q, "doc": d, "grade": int(statistics.median_low(gs)),
                        "by": "human", "graders": len(gs)}) + "\n"
            for (q, d), gs in sorted(human.items())))


if __name__ == "__main__":
    main()
