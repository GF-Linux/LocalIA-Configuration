from datagen.run_datagen import run_generation, pilot_projection
from datagen.budget import Budget

def _valid_hint_reply(msgs):
    return '{"comment":"c","why":"w","nudge":"n","suggestion":"s"}'

def test_run_generation_stops_when_budget_over():
    # teto $0.30; cada chamada custa $0.10 (1M completion tokens a $0.10/M no preço de teste)
    budget = Budget(ceiling_usd=0.30, price={"prompt": 0.0, "completion": 0.10})
    items = [{"code": f"def f{i}():\n return {i}", "lang": "python"} for i in range(100)]

    def ask(msgs):
        budget.charge({"prompt_tokens": 0, "completion_tokens": 1_000_000})  # $0.10
        return _valid_hint_reply(msgs)

    out = run_generation(items, ask, budget, "hint")
    # para quando spent >= 0.30: gera 3 (0.10, 0.20, 0.30) e na 4ª iteração over() corta
    assert len(out) == 3
    assert all("hint" in r for r in out)

def test_run_generation_skips_invalid_without_extra_budget_logic():
    budget = Budget(ceiling_usd=100.0, price={"prompt": 0.0, "completion": 0.0})
    items = [{"code": "a", "lang": "python"}, {"code": "b", "lang": "python"}]
    replies = iter(['{"comment":"c","why":"w","nudge":"n","suggestion":"s"}', "lixo"])
    out = run_generation(items, lambda m: next(replies), budget, "hint")
    assert len(out) == 1

def test_pilot_projection_computes_cost_per_valid_and_target():
    budget = Budget(ceiling_usd=4.0, price={"prompt": 0.0, "completion": 1.0})
    budget.charge({"prompt_tokens": 0, "completion_tokens": 100_000})  # $0.10
    proj = pilot_projection(budget, n_valid=50, ceiling=4.0)
    assert proj["n_valid"] == 50
    assert round(proj["spent"], 4) == 0.10
    assert round(proj["per_valid"], 5) == 0.002
    assert proj["projected_valid_for_ceiling"] == 2000
