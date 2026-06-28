import subprocess

def run_one(problem: dict, completion: str, executor) -> bool:
    program = (
        problem["prompt"] + completion + "\n"
        + problem["test"] + "\n"
        + f"check({problem['entry_point']})\n"
    )
    return executor(program) == 0

def subprocess_executor(timeout: float):
    """Executa código gerado por LLM isolado, com timeout. ATENÇÃO: roda código
    arbitrário — usar só em máquina de dev confiável (WSL). timeout/erro -> rc!=0."""
    def execute(program: str) -> int:
        try:
            proc = subprocess.run(
                ["python", "-c", program],
                capture_output=True, timeout=timeout,
            )
            return proc.returncode
        except subprocess.TimeoutExpired:
            return 124
        except Exception:
            return 1
    return execute
