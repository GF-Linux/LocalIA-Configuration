import os
from fastapi import FastAPI
from app.config import get_zim_path

app = FastAPI(title="Professor Retrieval Service")

@app.get("/health")
def health():
    return {"status": "ok", "zim_loaded": os.path.exists(get_zim_path())}
