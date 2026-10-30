"""bounded markdown passages that keep the source intact"""
import re
from collections.abc import Callable


def structure_chunks(text: str, limit: int = 2400, overlap: int = 400,
                     warn: Callable[[str], None] = lambda _: None) -> list[str]:
    if not 0 <= overlap < limit:
        raise ValueError("overlap must be smaller than limit")
    # sections are hard boundaries, markdown rows never get split
    sections = re.split(r"(?m)(?=^#{1,6} |^<!-- page )", text)
    out = []
    for section in sections:
        rows = []
        offset = 0
        for line in section.splitlines(keepends=True):
            if "|" in line and len(line.rstrip("\r\n")) > limit:
                warn("Markdown table row exceeds passage limit; "
                     "quarantined from automated extraction")
                if offset:
                    rows.append(section[:offset])
                section = section[offset + len(line):]
                offset = 0
            else:
                offset += len(line)
        rows.append(section)
        for text_part in rows:
            start = 0
            lines = []
            pos = 0
            for line in text_part.splitlines(keepends=True):
                if "|" in line:
                    lines.append((pos, pos + len(line)))
                pos += len(line)
            while start < len(text_part):
                end = min(start + limit, len(text_part))
                for left, right in lines:
                    if left < end < right:
                        end = left
                        break
                if end <= start:
                    # a row of exactly limit characters plus newline
                    end = min(start + limit, len(text_part))
                if text_part[start:end].strip():
                    out.append(text_part[start:end])
                if end == len(text_part):
                    break
                following = max(start + 1, end - overlap)
                for left, right in lines:
                    if left < following < right:
                        following = left if left > start else right
                        break
                start = min(following, end)
    return out
