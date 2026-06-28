import json
from datagen.qa_sample import qa_report

_GOOD = json.dumps({"scores": {"socratic": 4, "why": 4, "concision": 4,
                               "relevance": 4, "correctness": 4}, "rationale": "r"})

def test_qa_report_judges_teachable_and_reports_skip_rate():
    rows = [
        {"code": "open('f')", "lang": "python",
         "hint": {"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"}},
        {"code": "x=1", "lang": "go", "hint": {"skip": True}},
    ]
    out = qa_report(rows, lambda prompt: _GOOD, n=10, seed=0)
    assert out["n_total"] == 2
    assert out["skip_rate"] == 0.5
    assert out["n_judged"] == 1          # só a ensinável foi ao juiz
    assert out["overall"] == 4.0
    assert out["by_lang"] == {"python": 1, "go": 1}

def test_qa_report_empty_when_no_teachable():
    rows = [{"code": "x=1", "lang": "python", "hint": {"skip": True}}]
    out = qa_report(rows, lambda prompt: _GOOD, n=10)
    assert out["n_judged"] == 0 and out["overall"] == 0.0
    assert out["skip_rate"] == 1.0

def test_qa_report_deterministic_sampling():
    rows = [{"code": f"def f{i}():\n return {i}", "lang": "python",
             "hint": {"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"}}
            for i in range(50)]
    a = qa_report(rows, lambda prompt: _GOOD, n=5, seed=9)
    b = qa_report(rows, lambda prompt: _GOOD, n=5, seed=9)
    assert a == b
