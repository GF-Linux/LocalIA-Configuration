# Sobe o serviço de retrieval. Defina PROFESSOR_ZIM_PATH se o .zim não estiver no default.
param([int]$Port = 8765)

# PowerShell 5.1 compatible: if PROFESSOR_ZIM_PATH is not set, use default
if (-not $env:PROFESSOR_ZIM_PATH) {
    $env:PROFESSOR_ZIM_PATH = "C:\acervo-llm\kiwix\stackoverflow.com_en_all_2023-11.zim"
}

& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port $Port
