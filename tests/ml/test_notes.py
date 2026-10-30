import json
from types import SimpleNamespace

from paper_trail.ml.notes import NoteWriter
from tests.profiles import HU


class _Client:
    """openai-shaped stub: answers from a list, records the prompts"""

    def __init__(self, answers):
        self.answers, self.prompts = list(answers), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.prompts.append(kw["messages"][0]["content"])
        msg = SimpleNamespace(content=self.answers.pop(0))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_notes_carry_the_model_as_author_and_skip_bad_json():
    good = json.dumps({"title_en": "M1.1.2 District heating upgrade",
                       "summary_en": "Modernise the district heating network.",
                       "suggestion": "accept", "reason_en": "a concrete measure"})
    client = _Client([good, "not json"])
    notes = NoteWriter(client, "own-qwen3-awq", HU).write(
        [("candidate", 7, "M1.1.2 Távhőszolgáltatás fejlesztése"), ("link", 9, "x")])
    assert [(n.subject_kind, n.subject_id, n.suggestion, n.author) for n in notes] == [
        ("candidate", 7, "accept", "own-qwen3-awq")]
    # the glossary goes into the prompt so the model knows what M/A/Sz mean
    assert "mitigation" in client.prompts[0]
