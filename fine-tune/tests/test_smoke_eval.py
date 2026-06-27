from ftlib.smoke_eval import extract_json, score
from ftlib.format_chatml import TUTOR_SYSTEM

def test_extract_json_tolerates_junk():
    assert extract_json('lixo {"comment":"c"} fim') == {"comment": "c"}
    assert extract_json("sem json") is None

def _rec(code):
    return {"messages": [
        {"role": "system", "content": TUTOR_SYSTEM},
        {"role": "user", "content": code},
        {"role": "assistant", "content": "{}"},
    ]}

def test_score_counts_valid_json_hints():
    held = [_rec("a"), _rec("b"), _rec("c")]
    # asker devolve: 2 válidos, 1 inválido
    replies = iter([
        '{"comment":"c","why":"w","nudge":"n","suggestion":"s"}',
        'isso não é json',
        '{"skip": true}',
    ])
    def asker(messages):  # ignora o conteúdo, devolve a próxima resposta
        return next(replies)
    out = score(held, asker)
    assert out == {"total": 3, "valid": 2, "frac": 2/3}

def test_score_ignores_non_tutor_records():
    code_rec = {"messages": [
        {"role": "system", "content": "You are a helpful coding assistant. Answer the task with correct code."},
        {"role": "user", "content": "Write f"},
        {"role": "assistant", "content": "def f(): pass"},
    ]}
    def asker(messages):
        return "qualquer coisa"
    out = score([code_rec], asker)
    assert out == {"total": 0, "valid": 0, "frac": 0.0}
