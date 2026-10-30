"""the workspace: one table of commitments by kind, a detail pane, bulk actions, j/k keys.
the row model and wording live in workspace.py"""

from __future__ import annotations

import re
from functools import partial
from itertools import zip_longest

from fastapi.responses import RedirectResponse
from nicegui import app, ui

from ..domain.enums import ReviewStatus
from . import actions
from .workspace import (
    BUDGET_LABEL,
    FLAG_HELP,
    FLAG_LABEL,
    JURISDICTION_LABEL,
    KIND_LABEL,
    KIND_ORDER,
    KIND_SECTION,
    KIND_TONE,
    POLARITY_LABEL,
    REL_HELP,
    REL_LABEL,
    REL_TONE,
    STAGES,
    STATUS_LABEL,
    STATUS_SENTENCE,
    STATUS_TONE,
    Row,
    display_title,
    evidence_kind,
    goal,
    huf,
    matches_filter,
    page_link,
    shown,
)

# relationship -> trail bucket, everything else counts as supporting
BUCKET = {"direct_implementation": "Implementation", "budget": "Budget",
          "probably_unrelated": "Probably unrelated"}
TYPE_FILTER = {"all": "All types", "objective": "Objectives", "target": "Targets",
               "measure": "Measures", "indicator": "Indicators"}


def chip(text: str, tone: str = "grey", tip: str | None = None) -> None:
    c = ui.badge(text, color=f"{tone}-1", text_color=f"{tone}-9").classes("text-xs")
    if tip:
        c.tooltip(tip)


def toast_error(exc: Exception) -> None:
    ui.notify(str(exc), type="negative")


def key() -> str:
    return app.storage.user.get("review_key", "")


def english() -> bool:
    return app.storage.user.get("lang", "en") == "en"


def bi(text: str, en: str | None = None, cls: str = "") -> None:
    """original + plain-english side by side, the english is always labelled as such"""
    if not english():
        ui.label(text).classes(cls)
        return
    if en:
        with ui.row().classes("items-center gap-1 no-wrap"):
            ui.label(en).classes(cls)
            chip("AI", "grey", "written by the model, a reading aid")
        ui.label(f"ORIGINAL {text}").classes("text-xs text-grey-7")
    else:
        ui.label(text).classes(cls)
        ui.label("not translated yet").classes("text-xs text-grey-6")


def code_hint(code: str | None) -> None:
    m = re.match(r"^([A-Za-z]+)(\d+(?:\.\d+)*)", code or "")
    meaning = actions.glossary().get(m.group(1)) if m else None
    if meaning:
        depth = len(m.group(2).split("."))
        ui.label(f"what does {code} mean?").classes("text-xs underline text-grey-7").tooltip(
            f"{m.group(1)} = {meaning}. {depth} levels deep in the plan")


def note_card(note) -> None:
    if note is None:
        return
    tone = {"accept": "green", "reject": "red", "unsure": "amber"}[note.suggestion]
    with ui.card().classes("w-full bg-grey-1"):
        ui.label("In plain English").classes("text-sm font-medium")
        ui.label(note.summary_en)
        chip(f"AI suggests: {note.suggestion}", tone)
        if note.reason_en:
            ui.label(note.reason_en).classes("text-sm")
        ui.label(f"written by {note.author}. a suggestion only, you decide").classes(
            "text-xs text-grey-6")


class Workspace:
    """one per browser tab: filters, cursor, selection, the jobs it's watching"""

    def __init__(self, q: str, stage: str, kind: str) -> None:
        self.q, self.stage, self.kind = q, stage, kind
        self.cursor: int | None = None
        self.selected: set[int] = set()
        self.picked: dict[int, int] = {}  # row id -> source mention shown
        self.search_jobs: list[str] = []
        self.ingest_jobs: list[str] = actions.active_jobs("ingest")
        self.snap = actions.load()
        # pick up searches a reload or another tab started
        self.search_jobs = actions.active_jobs("find_evidence")

    # --- data

    def reload(self) -> None:
        self.snap = actions.load()
        self.view.refresh()

    def visible(self) -> list[Row]:
        return [r for r in self.snap.rows if matches_filter(r, self.stage, self.kind, self.q)]

    def current(self) -> Row | None:
        rows = {r.id: r for r in self.snap.rows}
        return rows.get(self.cursor) if self.cursor is not None else None

    def set_filter(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self, k, v)
        params = {"q": self.q, "stage": self.stage, "type": self.kind}
        # defaults stay out of the url, like before
        query = "&".join(f"{k}={v}" for k, v in params.items()
                         if v and v != {"q": "", "stage": "all", "type": "all"}[k])
        ui.navigate.history.replace(f"/?{query}" if query else "/")
        self.view.refresh()

    # --- actions

    def run(self, fn, *args, ok: str | None = None):
        try:
            out = fn(key(), *args)
        except actions.ActionError as exc:
            toast_error(exc)
            return None
        if ok:
            ui.notify(ok, type="positive")
        self.reload()
        return out

    def confirm(self, row: Row) -> None:
        c = shown(row, self.picked.get(row.id))
        if row.stage == "confirm" and c.review_status == ReviewStatus.UNREVIEWED:
            self.run(actions.accept, c.id, ok="Confirmed as a commitment.")

    def reject(self, row: Row) -> None:
        c = shown(row, self.picked.get(row.id))
        if row.stage == "confirm" and c.review_status == ReviewStatus.UNREVIEWED:
            self.run(actions.reject, c.id, ok="Rejected.")

    def picked_rows(self) -> list[Row]:
        return [r for r in self.snap.rows if r.id in self.selected]

    def bulk_mentions(self, confirm: bool) -> None:
        ids = [c.id for r in self.picked_rows() if r.stage == "confirm" for c in r.group
               if c.review_status == ReviewStatus.UNREVIEWED]
        accept, reject = (ids, []) if confirm else ([], ids)
        verb = "confirmed" if confirm else "rejected"
        if self.run(actions.bulk_candidates, accept, reject,
                    ok=f"{len(ids)} source mentions {verb}.") is not None:
            self.clear_selection()

    def bulk_matches(self, confirm: bool) -> None:
        ids = [lv.link.id for r in self.picked_rows() if r.stage == "review" for lv in r.pending]
        accept, reject = (ids, []) if confirm else ([], ids)
        noun = "match" if len(ids) == 1 else "matches"
        verb = "confirmed" if confirm else "rejected"
        if self.run(actions.bulk_links, accept, reject,
                    ok=f"{len(ids)} {noun} {verb}.") is not None:
            self.clear_selection()

    def bulk_search(self) -> None:
        if self.search([m.id for r in self.picked_rows() if r.stage == "search"
                        for m in r.commitments]):
            self.clear_selection()

    def clear_selection(self) -> None:
        self.selected.clear()
        self.view.refresh()

    def search(self, commitment_ids: list[int]) -> bool | None:
        # one after another, the first failure stops the rest
        for cid in commitment_ids:
            try:
                self.search_jobs.append(actions.find_evidence(key(), cid))
            except actions.ActionError as exc:
                ui.notify(f"Could not start search: {exc}", type="negative")
                return None
        self.view.refresh()
        return True

    def poll(self) -> None:
        """every 2s: settle finished searches and ingests, toast what happened"""
        if self.search_jobs and self._settle(self.search_jobs, self._search_done):
            self.search_jobs = []
        if self.ingest_jobs and self._settle(self.ingest_jobs, self._ingest_done):
            self.ingest_jobs = []
            self.header.refresh()

    def _settle(self, ids: list[str], done) -> bool:
        jobs = [j for j in map(actions.job, ids) if j is not None]
        if any(j.status not in ("done", "failed") for j in jobs):
            self.view.refresh()  # progress text
            return False
        if failed := [j for j in jobs if j.status == "failed"]:
            done(failed=failed)
        else:
            done(results=[j.result or {} for j in jobs])
            for w in (w for j in jobs for w in (j.result or {}).get("warnings", [])):
                ui.notify(w, type="warning")
        self.reload()
        return True

    @staticmethod
    def _search_done(failed=(), results=()) -> None:
        if failed:
            n = len(failed)
            ui.notify(f"{n} {'search' if n == 1 else 'searches'} failed: "
                      f"{failed[0].error or 'unknown'}", type="negative")
        elif total := sum(r.get("links", 0) for r in results):
            ui.notify(f"Search done: {total} possible matches.", type="positive")
        else:
            ui.notify("Search done: nothing useful on the official sites.", type="positive")

    @staticmethod
    def _ingest_done(failed=(), results=()) -> None:
        if failed:
            ui.notify(f"Ingest failed: {failed[0].error or 'unknown error'}", type="negative")
        else:
            ui.notify("Strategy read. Review the commitments it produced.", type="positive")

    def on_key(self, e) -> None:
        if not e.action.keydown:
            return
        rows = self.visible()
        ids = [r.id for r in rows]
        k = e.key.name
        if k in ("j", "k") and ids:
            i = ids.index(self.cursor) if self.cursor in ids else -1
            i = min(i + 1, len(ids) - 1) if k == "j" else max(i - 1, 0)
            self.cursor = ids[i]
            self.view.refresh()
        elif k == "/":
            self.search_box.run_method("focus")
        elif (row := self.current()) is not None:
            if k == "x":
                self.selected.symmetric_difference_update({row.id})
                self.view.refresh()
            elif k == "c":
                self.confirm(row)
            elif k == "r":
                self.reject(row)
            elif k == "s" and row.stage == "search" and not self.search_jobs:
                self.search([m.id for m in row.commitments])

    # --- views

    @ui.refreshable_method
    def header(self) -> None:
        with ui.row().classes("w-full items-center gap-3"):
            ui.label("Paper Trail").classes("text-lg font-semibold")
            if dep := actions.deployment():
                chip(dep, "grey")
            ui.space()
            lang = actions.language_name() or "Original"
            ui.toggle({"en": "English", "orig": lang}, value=app.storage.user.get("lang", "en"),
                      on_change=lambda e: (app.storage.user.update(lang=e.value),
                                           self.view.refresh())).props("dense no-caps")
            if actions.glossary():
                ui.button("Glossary", on_click=self.glossary_dialog).props("flat dense no-caps")
            if actions.review_required():
                ui.button("Review key", on_click=self.key_dialog).props("flat dense no-caps")
            if self.ingest_jobs:
                j = actions.job(self.ingest_jobs[0])
                with ui.row().classes("items-center gap-1"):
                    ui.spinner(size="sm")
                    ui.label((j and j.progress) or "Reading strategy…").classes("text-sm")
            else:
                ui.button("Ingest", icon="upload_file",
                          on_click=self.ingest_dialog).props("outline dense no-caps")
            dark = ui.dark_mode(None)
            ui.button(icon="dark_mode", on_click=dark.toggle).props("flat dense round")

    def glossary_dialog(self) -> None:
        with ui.dialog() as d, ui.card().classes("w-[32rem]"):
            ui.label("Glossary").classes("text-lg")
            for term, meaning in actions.glossary().items():
                with ui.row().classes("no-wrap gap-2"):
                    ui.label(term).classes("font-mono w-24 shrink-0")
                    ui.label(meaning)
        d.open()

    def key_dialog(self) -> None:
        with ui.dialog() as d, ui.card().classes("w-96"):
            ui.label("Review key").classes("text-lg")
            ui.label("This deployment requires a key to confirm or reject items. "
                     "It is stored only for this browser.").classes("text-sm")
            box = ui.input(password=True, value=key()).classes("w-full")

            def save():
                value = (box.value or "").strip()
                app.storage.user["review_key"] = value
                ui.notify("Review key saved" if value else "Review key cleared")
                d.close()
            ui.button("Save", on_click=save)
        d.open()

    def ingest_dialog(self) -> None:
        names = actions.available_documents()
        with ui.dialog() as d, ui.card().classes("w-[28rem]"):
            ui.label("Read a strategy").classes("text-lg")
            name = (ui.select(names, label="Document").classes("w-full") if names else
                    ui.input("Document", placeholder="filename.pdf").classes("w-full"))
            title = ui.input("Title").classes("w-full")
            publisher = ui.input("Publisher").classes("w-full")
            url = ui.input("Official URL (optional)").classes("w-full")

            def start():
                if not name.value:
                    ui.notify("Pick a document", type="warning")
                    return
                if not (title.value or "").strip():
                    ui.notify("Title required", type="warning")
                    return
                try:
                    self.ingest_jobs.append(actions.ingest(key(), name.value, title.value.strip(),
                                                           publisher.value or "", url.value or ""))
                except actions.ActionError as exc:
                    ui.notify(f"Ingest failed: {exc}", type="negative")
                    return
                d.close()
                self.header.refresh()
            ui.button("Start reading", on_click=start).bind_enabled_from(name, "value")
        d.open()

    @ui.refreshable_method
    def view(self) -> None:
        rows = self.snap.rows
        if not rows:
            with ui.column().classes("w-full items-center p-12"):
                ui.label("Nothing extracted yet").classes("text-lg")
                ui.label("Use Ingest in the top bar to read the strategy PDF.")
            return
        self.toolbar(rows)
        with ui.splitter(value=68, limits=(45, 78)).classes("w-full") as split:
            with split.before:
                self.table()
            with split.after:
                with ui.column().classes("w-full p-3 gap-3"):
                    row = self.current()
                    if row is None:
                        ui.label("Select a commitment to see its detail.").classes("text-grey-7")
                    else:
                        self.detail(row)

    def toolbar(self, rows: list[Row]) -> None:
        with ui.row().classes("w-full items-center gap-3"):
            self.search_box = ui.input(placeholder="Search commitments", value=self.q).props(
                "dense outlined clearable debounce=250").classes("w-72")
            self.search_box.on_value_change(lambda e: self.set_filter(q=e.value or ""))
            ui.select(TYPE_FILTER, value=self.kind,
                      on_change=lambda e: self.set_filter(kind=e.value)).props("dense outlined")
            ui.label("j k move · x select · c confirm · r reject · s search · / find").classes(
                "text-xs text-grey-6")
        counts = {s: sum(r.stage == s for r in rows) for s in STAGES}
        with ui.row().classes("gap-2"):
            all_n = len(rows) - counts["rejected"]
            ui.button(f"All {all_n}", on_click=lambda: self.set_filter(stage="all")).props(
                f"{'unelevated' if self.stage == 'all' else 'outline'} dense no-caps").tooltip(
                "Everything except rejected")
            for s, (label, hint, tone) in STAGES.items():
                ui.button(f"{label} {counts[s]}", color=tone,
                          on_click=lambda s=s: self.set_filter(stage=s)).props(
                    f"{'unelevated' if self.stage == s else 'outline'} dense no-caps").tooltip(hint)
        if self.selected:
            picked = self.picked_rows()
            stages = {r.stage for r in picked}
            mentions, matches = self.bulk_mentions, self.bulk_matches
            with ui.row().classes("items-center gap-2 p-2 bg-grey-2 rounded"):
                ui.label(f"{len(self.selected)} selected")
                if "confirm" in stages:
                    n = sum(r.stage == "confirm" for r in picked)
                    ui.button(f"Confirm {n}", on_click=partial(mentions, True)).props("dense")
                    ui.button("Reject", on_click=partial(mentions, False)).props("dense flat")
                if "search" in stages:
                    n = sum(r.stage == "search" for r in picked)
                    ui.button(f"Find evidence {n}", on_click=self.bulk_search).props("dense")
                if "review" in stages:
                    ui.button("Confirm matches",
                              on_click=partial(matches, True)).props("dense")
                    ui.button("Reject", on_click=partial(matches, False)).props("dense flat")
                ui.button("Clear", on_click=self.clear_selection).props("dense flat")
        if self.search_jobs:
            n = len(self.search_jobs)
            with ui.row().classes("items-center gap-2 p-2 bg-blue-1 rounded"):
                ui.spinner(size="sm")
                ui.label(f"Finding evidence ({n} {'job' if n == 1 else 'jobs'})")
                for j in filter(None, map(actions.job, self.search_jobs)):
                    if j.progress:
                        ui.label(j.progress).classes("text-xs text-grey-7")

    def table(self) -> None:
        visible = self.visible()
        if not visible:
            ui.label("Nothing matches these filters.").classes("p-4 text-grey-7")
            return
        columns = [
            {"name": "commitment", "label": "Commitment", "field": "commitment", "align": "left"},
            {"name": "stage", "label": "Stage", "field": "stage", "align": "left"},
            {"name": "evidence", "label": "Evidence", "field": "evidence", "align": "left"},
            {"name": "page", "label": "Page", "field": "page"},
            {"name": "goal", "label": "Goal", "field": "goal", "align": "left"},
        ]
        for kind in KIND_ORDER:
            rows = [r for r in visible if r.kind == kind]
            if not rows:
                continue
            with ui.expansion(f"{KIND_SECTION[kind]} ({len(rows)})", value=True).classes("w-full"):
                data = [self.table_row(r) for r in rows]
                t = ui.table(columns=columns, rows=data, row_key="id", selection="multiple",
                             on_select=lambda e, rows=rows: self.on_select(rows, e.selection))
                t.selected = [d for d in data if d["id"] in self.selected]
                t.props("flat dense wrap-cells").classes("w-full")
                t.on("rowClick", lambda e: self.open(e.args[1]["id"]))

    def table_row(self, r: Row) -> dict:
        c = shown(r, self.picked.get(r.id))
        title = display_title(r.title)
        if english() and c.note is not None and c.note.title_en:
            title = f"{c.note.title_en}  ·  {title}"
        ev = []
        if r.evidence:
            ev.append(f"✓{r.evidence}")
        if r.pending:
            ev.append(f"{len(r.pending)} to review")
        return {"id": r.id, "commitment": ("▶ " if r.id == self.cursor else "") + title,
                "stage": STAGES[r.stage][0], "evidence": " ".join(ev) or "–",
                "page": c.source_page, "goal": goal(c)}

    def on_select(self, rows: list[Row], selection: list[dict]) -> None:
        # each kind section is its own table, keep the union
        self.selected -= {r.id for r in rows}
        self.selected |= {d["id"] for d in selection}
        self.view.refresh()

    def open(self, row_id: int) -> None:
        self.cursor = row_id
        self.view.refresh()

    # --- detail pane

    def detail(self, row: Row) -> None:
        c = shown(row, self.picked.get(row.id))
        with ui.row().classes("items-center gap-2"):
            chip(KIND_LABEL[row.kind], KIND_TONE[row.kind])
            label, hint, tone = STAGES[row.stage]
            chip(label, tone, hint)
            text, href = page_link(self.snap.doc_urls.get(c.document_id), c.source_page)
            if href:
                ui.link(text, href, new_tab=True).classes("text-sm")
            else:
                ui.label(text).classes("text-sm")
        bi(display_title(row.title), c.note.title_en if c.note else None,
           "text-base font-medium")
        code_hint(c.code)
        if len(row.group) > 1:
            self.mention_picker(row, c)
        if row.stage == "confirm":
            self.candidate_detail(row, c)
            return
        if row.searchable and row.commitments:
            again = row.pending or row.evidence
            ui.button("Search again" if again else "Find evidence", icon="travel_explore",
                      on_click=lambda: self.search([m.id for m in row.commitments])).props(
                "outline dense no-caps").set_enabled(not self.search_jobs)
        if row.pending:
            ui.label("Matches to review").classes("text-sm font-medium mt-2")
            for lv in sorted(row.pending, key=lambda v: v.link.score, reverse=True):
                self.match_card(lv.link.id)
        ui.label(f"Paper trail ({row.evidence})").classes("text-sm font-medium mt-2")
        if row.trail:
            for t in row.trail:
                self.trail_detail(t, c)
        else:
            ui.label("Nothing recorded for this commitment.").classes("text-grey-7")

    def mention_picker(self, row: Row, c) -> None:
        def label(m) -> str:
            status = {"accepted": "confirmed", "rejected": "rejected"}.get(
                m.review_status.value, "needs review")
            return f"p.{m.source_page} · {status} · mention {m.id}"
        ui.select({m.id: label(m) for m in row.group}, value=c.id, label="Source mention",
                  on_change=lambda e: (self.picked.__setitem__(row.id, e.value),
                                       self.view.refresh())).props("dense outlined")

    def candidate_detail(self, row: Row, c) -> None:
        if c.review_status == ReviewStatus.ACCEPTED:
            chip("Confirmed", "green")
        elif c.review_status == ReviewStatus.REJECTED:
            chip("Rejected", "red")
        elif c.excerpt_on_page is False:
            chip("Unclear", "grey")
            ui.label("We couldn't re-find this quote on the page — worth a closer look.").classes(
                "text-sm text-amber-9")
        else:
            chip("Needs review", "amber")
        note_card(c.note)
        with ui.card().classes("w-full"):
            ui.label("The strategy says").classes("text-xs text-grey-7")
            ui.label(f"“{c.source_excerpt}”").classes("italic")
        if c.review_status != ReviewStatus.UNREVIEWED:
            return
        with ui.row().classes("gap-2"):
            ui.button("Confirm", icon="check", on_click=lambda: self.confirm(row)).props("dense")
            ui.button("Reject", icon="close", color="negative",
                      on_click=lambda: self.reject(row)).props("dense outline")
        with ui.expansion("Edit before confirming").classes("w-full"):
            kind = ui.select({k: KIND_LABEL[k] for k in KIND_ORDER}, value=c.suggested_type.value,
                             label="Type").classes("w-full")
            title = ui.input("Title", value=display_title(c.normalized_title),
                             validation={"Enter a short name": lambda v: bool((v or "").strip())}
                             ).classes("w-full")
            parents = {0: "— on its own —"} | {
                m.id: f"{m.code + ' · ' if m.code else ''}{display_title(m.title)} [{m.id}]"
                for m in self.snap.commitments}
            parent = ui.select(parents, value=0, label="Part of").classes("w-full")

            def save():
                if not (title.value or "").strip():
                    return
                self.run(actions.accept, c.id, kind.value, title.value.strip(),
                         parent.value or None, ok="Saved as a commitment.")
            ui.button("Save as commitment", on_click=save).props("dense")

    def match_card(self, link_id: int) -> None:
        lv = actions.link_detail(link_id)
        link, ev = lv.link, lv.evidence
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center gap-2"):
                chip(f"{link.score:.2f}", "grey", "match score")
                chip(REL_LABEL[link.suggested_relationship.value],
                     REL_TONE[link.suggested_relationship.value])
                if ev:
                    chip(evidence_kind(ev.url, ev.title), "grey")
            if ev:
                ui.link(ev.title or ev.url, ev.url, new_tab=True).classes("font-medium")
                if ev.publisher or ev.published_on:
                    ui.label(" · ".join(str(x) for x in (ev.publisher, ev.published_on) if x)
                             ).classes("text-xs text-grey-7")
                self.evidence_warnings(ev)
                ui.label(STATUS_SENTENCE[ev.status_hint.value]).classes("text-sm")
                if ev.status_excerpt or ev.snippet:
                    ui.label(f"“{ev.status_excerpt or ev.snippet}”").classes("text-sm italic")
            note_card(lv.note)
            with ui.expansion("Details").classes("w-full"):
                ui.label("Why Paper Trail matched it").classes("text-xs text-grey-7")
                ui.label("; ".join(link.reasons) or "No matching explanation stored.").classes(
                    "text-sm")
                for flag in ev.flags if ev else []:
                    ui.label(f"{FLAG_LABEL[flag.value]}: {FLAG_HELP[flag.value]}").classes(
                        "text-sm text-amber-9")
                if lv.budgets:
                    ui.label("Money mentioned").classes("text-xs text-grey-7")
                    for b in lv.budgets[:4]:
                        self.budget_line(b)
                rel = ui.select({k: REL_LABEL[k] for k in REL_LABEL},
                                value=link.suggested_relationship.value,
                                label="Relationship").classes("w-full")
                ui.label(REL_HELP[link.suggested_relationship.value]).classes(
                    "text-xs text-grey-7")
                ui.label("Applied when you confirm this selected match.").classes(
                    "text-xs text-grey-6")
            with ui.row().classes("gap-2"):
                ui.button("Confirm", icon="check", on_click=lambda: self.run(
                    actions.decide_link, link.id, True, rel.value, ok="Match confirmed.")).props(
                    "dense")
                ui.button("Reject", icon="close", color="negative", on_click=lambda: self.run(
                    actions.decide_link, link.id, False, ok="Match rejected.")).props(
                    "dense outline")

    @staticmethod
    def evidence_warnings(ev) -> None:
        with ui.row().classes("gap-1"):
            if POLARITY_LABEL.get(ev.polarity.value):
                chip(POLARITY_LABEL[ev.polarity.value], "red")
            for flag in ev.flags:
                chip(FLAG_LABEL[flag.value], "red" if flag.value == "regression_warning"
                     else "amber", FLAG_HELP[flag.value])
            for pid in ev.procurement_ids:
                chip(pid, "grey")

    @staticmethod
    def budget_line(b) -> None:
        amount = huf(b.amount_huf) if b.currency == "HUF" else b.amount_raw
        bits = [BUDGET_LABEL[b.kind.value], amount, str(b.fiscal_year or "")]
        ui.label(" · ".join(x for x in bits if x)).classes("text-sm")

    def trail_detail(self, t, c) -> None:
        com = t.commitment
        meta = [com.kind.value.upper()]
        if com.deadline_year:
            meta.append(f"Deadline {com.deadline_year}")
        if com.target_value is not None and com.unit:
            meta.append(f"Target {com.target_value:g} {com.unit}")
        if com.responsible_org:
            meta.append(f"who: {com.responsible_org}")
        ui.label(" · ".join(meta)).classes("text-xs text-grey-7")
        with ui.row().classes("items-center gap-2"):
            if t.status.value != "unknown":
                chip(f"Source says: {STATUS_LABEL[t.status.value]}",
                     STATUS_TONE.get(t.status.value, "grey"))
            ui.select({k: v for k, v in JURISDICTION_LABEL.items()},
                      value=com.asset_owner_jurisdiction.value, label="Asset owner",
                      on_change=lambda e: self.run(
                          actions.set_jurisdiction, com.id, e.value,
                          ok="Owner updated. The next evidence search covers their sites.")
                      ).props("dense outlined")
        if t.financial_states:
            states = " → ".join(BUDGET_LABEL[s.value] for s in t.financial_states)
            done = "spending confirmed" if t.financially_executed else "spending not confirmed"
            ui.label(f"Money on record: {states} · {done}").classes("text-sm")
        buckets: dict[str, list] = {"Implementation": [], "Supporting": [], "Budget": [],
                                    "Probably unrelated": []}
        for ev, rel in zip_longest(t.evidence, t.relationships[:len(t.evidence)]):
            buckets[BUCKET.get(rel.value if rel else "", "Supporting")].append(ev)
        tones = {"Implementation": "green", "Supporting": "blue", "Budget": "purple",
                 "Probably unrelated": "grey"}
        for name, items in buckets.items():
            if not items and not (name == "Budget" and t.budgets):
                continue
            with ui.card().classes(f"w-full border-l-4 border-{tones[name]}-5"):
                ui.label(name).classes("text-sm font-medium")
                if name == "Implementation" and t.status_excerpt:
                    ui.label(f"“{t.status_excerpt}”").classes("text-sm italic")
                for ev in items:
                    ui.link(ev.title or ev.url, ev.url, new_tab=True).classes("text-sm")
                    self.evidence_warnings(ev)
                if name == "Budget":
                    for b in t.budgets[:6]:
                        self.budget_line(b)
                    if len(t.budgets) > 6:
                        ui.label(f"… and {len(t.budgets) - 6} more figures in the sources"
                                 ).classes("text-xs text-grey-7")
        for title, items, tone in (("Audit findings", t.findings, "red"),
                                   ("Still missing", t.gaps, "amber")):
            if items:
                with ui.card().classes(f"w-full border-l-4 border-{tone}-5"):
                    ui.label(title).classes("text-sm font-medium")
                    for x in items:
                        ui.label(x).classes("text-sm")


@ui.page("/")
def workspace(q: str = "", stage: str = "all", type: str = "all") -> None:  # noqa: A002
    stage = stage if stage in STAGES or stage == "all" else "all"
    w = Workspace(q, stage, type if type in TYPE_FILTER else "all")
    with ui.header().classes("bg-white text-black shadow-sm"):
        w.header()
    with ui.column().classes("w-full max-w-[1400px] mx-auto gap-3"):
        ui.label("Check each promise against the strategy, find official sources, "
                 "confirm what they show.").classes("text-sm text-grey-7")
        w.view()
    ui.keyboard(on_key=w.on_key)
    ui.timer(2.0, w.poll)


# old app's bookmarks still land in the right stage
for _old, _stage in (("commitments", "confirm"), ("evidence", "review"), ("trail", "done")):
    app.add_api_route(f"/{_old}", lambda s=_stage: RedirectResponse(f"/?stage={s}"),
                      include_in_schema=False)
