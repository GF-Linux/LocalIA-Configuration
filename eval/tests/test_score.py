from evallib.score import compute_gates, verdict, GATE_THRESHOLDS, format_report

_PASS = {
    "format": {"ft": 0.97, "base": 0.99},
    "quality": {"overall_ft": 4.1, "overall_base": 3.6},
    "ab": {"ft_wins": 22, "base_wins": 10, "ties": 8},
    "code": {"ft": 0.71, "base": 0.74},
    "selectivity": {"correct": 6, "total": 8},
}

def test_all_gates_pass_promotes():
    g = compute_gates(_PASS)
    assert g == {"G0": True, "G1": True, "G2": True, "G3": True}
    assert verdict(g) == "PROMOVER"

def test_g0_format_below_threshold_fails():
    r = {**_PASS, "format": {"ft": 0.90, "base": 0.99}}
    assert compute_gates(r)["G0"] is False
    assert verdict(compute_gates(r)) == "NAO_PROMOVER"

def test_g1_fails_when_ab_not_positive():
    r = {**_PASS, "ab": {"ft_wins": 10, "base_wins": 22, "ties": 8}}
    assert compute_gates(r)["G1"] is False

def test_g1_fails_when_rubric_below_base():
    r = {**_PASS, "quality": {"overall_ft": 3.4, "overall_base": 3.6}}
    assert compute_gates(r)["G1"] is False

def test_g2_code_regression_within_epsilon_passes():
    # ft 0.70 vs base 0.74 → diff 0.04 <= eps 0.05 → passa
    r = {**_PASS, "code": {"ft": 0.70, "base": 0.74}}
    assert compute_gates(r)["G2"] is True

def test_g2_code_regression_beyond_epsilon_fails():
    r = {**_PASS, "code": {"ft": 0.60, "base": 0.74}}
    assert compute_gates(r)["G2"] is False

def test_g3_selectivity_below_half_fails():
    r = {**_PASS, "selectivity": {"correct": 3, "total": 8}}
    assert compute_gates(r)["G3"] is False

def test_thresholds_constant():
    assert GATE_THRESHOLDS["format_min"] == 0.95
    assert GATE_THRESHOLDS["code_eps"] == 0.05

def test_format_report_returns_str_with_verdict():
    g = compute_gates(_PASS)
    out = format_report(_PASS, g)
    assert isinstance(out, str)
    assert "PROMOVER" in out

def test_g3_zero_total_fails_no_crash():
    r = {**_PASS, "selectivity": {"correct": 0, "total": 0}}
    assert compute_gates(r)["G3"] is False  # guard: no ZeroDivisionError

def test_g0_at_threshold_passes():
    r = {**_PASS, "format": {"ft": 0.95, "base": 0.99}}
    assert compute_gates(r)["G0"] is True

def test_g2_exact_epsilon_boundary_passes():
    # ft = base - 0.05 exactly -> must pass (inclusive boundary).
    # Verified: 0.69 >= 0.74 - 0.05 is True in CPython float (no rounding hazard).
    r = {**_PASS, "code": {"ft": 0.69, "base": 0.74}}
    assert compute_gates(r)["G2"] is True

def test_g3_exactly_half_passes():
    r = {**_PASS, "selectivity": {"correct": 4, "total": 8}}
    assert compute_gates(r)["G3"] is True
