"""finding a quote on a pdf page, and drawing the page"""

import pytest

from paper_trail.sources import pdf_page
from paper_trail.sources.pdf_page import PdfUnavailable, locate, render
from tests.sources.pdfs import make_pdf

PAGE = make_pdf([
    "The city will plant 500 new trees by 2030",
    "and cut emissions from municipal buildings",
    "by 40 percent against the 2010 baseline.",
])


def test_a_quote_on_one_line_is_one_rectangle_inside_the_page():
    view = locate(PAGE, 1, "plant 500 new trees")
    assert view.found and len(view.boxes) == 1
    box = view.boxes[0]
    assert 0 < box.x < 1 and 0 < box.y < 1 and box.x + box.w <= 1 and box.y + box.h <= 1
    assert box.w < 0.5  # four words, not the whole line


def test_a_quote_across_lines_is_one_rectangle_per_line():
    view = locate(PAGE, 1, "500 new trees by 2030\nand cut emissions from municipal buildings")
    assert view.found and len(view.boxes) == 2
    assert view.boxes[0].y < view.boxes[1].y  # the second line is lower on the page


def test_line_breaks_hyphens_case_and_spacing_do_not_matter():
    assert locate(PAGE, 1, "THE   CITY will\n  plant 500-new trees").found


def test_a_quote_that_is_not_on_the_page_is_not_found():
    view = locate(PAGE, 1, "the council will build a new bridge")
    assert not view.found and view.boxes == []


def test_a_long_quote_that_goes_on_past_the_page_text_is_marked_up_to_what_matches():
    quote = "The city will plant 500 new trees by 2030 and then something the page never says"
    assert locate(PAGE, 1, quote).found


def test_a_page_that_does_not_exist_is_refused():
    with pytest.raises(PdfUnavailable):
        locate(PAGE, 2, "anything")
    with pytest.raises(PdfUnavailable):
        render(PAGE, 0)


def test_something_that_is_not_a_pdf_is_refused():
    with pytest.raises(PdfUnavailable):
        locate(b"%PDF-1.4 but not really", 1, "x")


def test_the_page_renders_as_a_small_webp():
    image = render(PAGE, 1)
    assert image[:4] == b"RIFF" and image[8:12] == b"WEBP"
    assert len(image) < 100_000


class _Response:
    def __init__(self, status=200, body=b"%PDF-1.4 ok"):
        self.status_code, self._body = status, body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_content(self, size):
        yield self._body


def test_only_a_pdf_from_the_documents_own_host_is_fetched(monkeypatch):
    seen = []
    def fetch(url, domains):
        seen.append((url, set(domains)))
        return _Response()

    monkeypatch.setattr(pdf_page, "safe_get", fetch)
    pdf_page.download.cache_clear()
    assert pdf_page.download("https://city.example/plan.pdf") == b"%PDF-1.4 ok"
    assert seen == [("https://city.example/plan.pdf", {"city.example"})]


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://city.example/plan.pdf", "city.example/plan.pdf"]
)
def test_only_web_addresses_are_fetched(url):
    pdf_page.download.cache_clear()
    with pytest.raises(PdfUnavailable):
        pdf_page.download(url)


def test_an_answer_that_is_not_a_pdf_is_refused(monkeypatch):
    page = _Response(body=b"<html>login</html>")
    monkeypatch.setattr(pdf_page, "safe_get", lambda url, domains: page)
    pdf_page.download.cache_clear()
    with pytest.raises(PdfUnavailable, match="not a pdf"):
        pdf_page.download("https://city.example/plan.pdf")


def test_a_file_over_the_cap_is_refused(monkeypatch):
    monkeypatch.setattr(pdf_page, "MAX_PDF_BYTES", 10)
    page = _Response(body=b"%PDF" + b"x" * 100)
    monkeypatch.setattr(pdf_page, "safe_get", lambda url, domains: page)
    pdf_page.download.cache_clear()
    with pytest.raises(PdfUnavailable, match="too large"):
        pdf_page.download("https://city.example/plan.pdf")
