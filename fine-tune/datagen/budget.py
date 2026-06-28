"""Contabilidade de custo com teto rígido. Puro (sem rede)."""

# USD por 1M tokens. PLACEHOLDER calibrado no piloto contra a página de preços do
# OpenRouter (z-ai/glm-5.2). O teto é conservador se o preço estiver superestimado.
GLM52_PRICE = {"prompt": 0.50, "completion": 1.50}


class Budget:
    def __init__(self, ceiling_usd: float, price: dict = GLM52_PRICE):
        self.ceiling_usd = float(ceiling_usd)
        self.price = price
        self._spent = 0.0
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def charge(self, usage: dict) -> float:
        pt = int(usage.get("prompt_tokens") or 0)
        ct = int(usage.get("completion_tokens") or 0)
        cost = pt / 1e6 * self.price["prompt"] + ct / 1e6 * self.price["completion"]
        self._spent += cost
        self.calls += 1
        self.prompt_tokens += pt
        self.completion_tokens += ct
        return cost

    def spent(self) -> float:
        return self._spent

    def over(self) -> bool:
        return self._spent >= self.ceiling_usd


def project_total(spent: float, n_done: int, ceiling: float) -> int:
    if n_done <= 0 or spent <= 0:
        return 0
    return int(n_done / spent * ceiling)
