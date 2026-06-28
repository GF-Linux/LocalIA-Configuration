from evallib.codegen import build_code_prompt, strip_code_fence, pass_at_1, load_subset_ids
from evallib.sandbox import run_one

def test_build_code_prompt_has_signature_no_tutor():
    p = build_code_prompt({"prompt": "def add(a, b):\n    \"\"\"soma\"\"\"\n"})
    assert "def add(a, b):" in p
    assert "professor" not in p.lower()  # não é o system de tutor

def test_strip_code_fence():
    assert strip_code_fence("```python\nx=1\n```") == "x=1"
    assert strip_code_fence("x=2") == "x=2"

def test_run_one_passes_for_correct_completion():
    problem = {
        "prompt": "def add(a, b):\n",
        "test": "def check(candidate):\n    assert candidate(2, 3) == 5\n",
        "entry_point": "add",
    }
    # executor finge rodar e devolve 0 (sucesso) — testa a montagem/contrato
    captured = {}
    def fake_exec(program):
        captured["program"] = program
        return 0
    assert run_one(problem, "    return a + b\n", fake_exec) is True
    assert "def add(a, b):" in captured["program"]
    assert "def check(candidate):" in captured["program"]
    assert "check(add)" in captured["program"]

def test_run_one_fails_when_executor_nonzero():
    problem = {"prompt": "def f():\n", "test": "def check(c):\n    pass\n", "entry_point": "f"}
    assert run_one(problem, "    return 1\n", lambda program: 1) is False

def test_pass_at_1_counts():
    problems = [{"prompt": "def f():\n", "test": "def check(c):\n    pass\n", "entry_point": "f"},
                {"prompt": "def g():\n", "test": "def check(c):\n    pass\n", "entry_point": "g"}]
    completions = ["    return 1\n", "    return 2\n"]
    rc = iter([0, 1])
    out = pass_at_1(problems, completions, lambda program: next(rc))
    assert out == {"passed": 1, "total": 2, "frac": 0.5}

def test_real_subset_file_loads():
    ids = load_subset_ids("data/humaneval_subset.txt")
    assert len(ids) >= 30
    assert all(i.startswith("HumanEval/") for i in ids)
