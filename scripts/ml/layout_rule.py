"""layout rule: a page with measure-sheet field labels holds a commitment

KEHOP-style strategies print every measure as a sheet with the same fields (owner,
deadline, cost, funding source, measure code). Counting those labels needs no model.
"""

import re

FIELDS = [r"Felel[őo]s", r"Határid[őo]", r"Időtáv", r"Finanszírozási\s+igény",
          r"Lehetséges\s+forrás", r"Célcsoport", r"Intézkedés\s+kódja", r"beavatkozás",
          r"Javasolt\s+intézkedések", r"Kapcsolódás"]


def field_count(text: str) -> int:
    return sum(bool(re.search(f, text, re.I)) for f in FIELDS)


def is_commitment_page(text: str, min_fields: int = 2) -> bool:
    return field_count(text) >= min_fields
