# Professor — Retrieval Service (StackOverflow offline)

Serviço HTTP que busca no `.zim` do StackOverflow e devolve JSON para a extensão.

## Rodar

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
$env:PROFESSOR_ZIM_PATH = "C:\acervo-llm\kiwix\stackoverflow.com_en_all_2023-11.zim"
.\serve.ps1            # http://0.0.0.0:8765
```

## API

- `GET /health` → `{"status":"ok","zim_loaded":true}`
- `GET /retrieve?q=python+read+file&k=3` → `[{"title","url","snippet"}]`

## Testes

```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```
