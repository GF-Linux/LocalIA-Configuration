from datagen.budget import Budget, project_total, GLM52_PRICE

def test_price_constant_shape():
    assert set(GLM52_PRICE) == {"prompt", "completion"}
    assert GLM52_PRICE["prompt"] > 0 and GLM52_PRICE["completion"] > 0

def test_charge_accumulates_cost_and_counters():
    b = Budget(ceiling_usd=1.0, price={"prompt": 1.0, "completion": 2.0})
    cost = b.charge({"prompt_tokens": 1_000_000, "completion_tokens": 500_000})
    # 1M*$1 + 0.5M*$2 = 1.0 + 1.0 = 2.0
    assert round(cost, 6) == 2.0
    assert round(b.spent(), 6) == 2.0
    assert b.calls == 1
    assert b.prompt_tokens == 1_000_000 and b.completion_tokens == 500_000

def test_charge_handles_missing_or_none_usage():
    b = Budget(ceiling_usd=1.0, price={"prompt": 1.0, "completion": 1.0})
    assert b.charge({}) == 0.0
    assert b.charge({"prompt_tokens": None, "completion_tokens": None}) == 0.0
    assert b.spent() == 0.0

def test_over_triggers_at_ceiling():
    b = Budget(ceiling_usd=0.5, price={"prompt": 1.0, "completion": 0.0})
    assert b.over() is False
    b.charge({"prompt_tokens": 600_000, "completion_tokens": 0})  # $0.60 >= $0.50
    assert b.over() is True

def test_project_total_scales_linearly():
    # gastou $0.10 para 50 válidos -> para $4.0 projeta 2000
    assert project_total(0.10, 50, 4.0) == 2000

def test_project_total_guards_zero():
    assert project_total(0.0, 0, 4.0) == 0
    assert project_total(0.0, 10, 4.0) == 0
