from fastapi import FastAPI
app = FastAPI(title="CRM Ultima")
@app.get("/health")
def health():
    return {"status": "ok"}
