# Professor — Régua de avaliação (Fatia B1)

Mede se um modelo do Professor ficou melhor, em 4 trilhas:
formato (JSON), qualidade pedagógica (Claude-juiz), A/B cego vs base, regressão de código (HumanEval).

## Ambiente
`pip install -r requirements.txt`
Juiz: exige a variável de ambiente `ANTHROPIC_API_KEY` (NÃO commitar a chave).
Geração: Ollama local em `http://localhost:11434` com os modelos a comparar.

## Pipeline
    python run_eval.py --models professor-ft qwen2.5-coder:14b
Gera um relatório lado a lado das 4 trilhas + veredito (PROMOVER / NÃO PROMOVER).
Rode trilhas isoladas com flags (ver `python run_eval.py --help`) para não gastar API.
