"""a pdf to test against, built by hand so no file has to be kept"""


def make_pdf(lines: list[str], rotate: int = 0, crop: str = "") -> bytes:
    """a one-page pdf, each line of text on its own line, in Helvetica 12 from 72 pt in;
    `rotate` sets /Rotate, `crop` a /CropBox such as 0 392 612 792"""
    text = " ".join(f"({line}) Tj T*" for line in lines)
    stream = f"BT /F1 12 Tf 72 720 Td 14 TL {text} ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        f"{f' /Rotate {rotate}' if rotate else ''}{f' /CropBox [{crop}]' if crop else ''}"
        " /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(out)
