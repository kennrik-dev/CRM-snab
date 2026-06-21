from fastapi import FastAPI

from app.routers import auth, dict, search, users

app = FastAPI(title="CRM Ultima")
app.include_router(auth.router)
app.include_router(dict.router)
app.include_router(users.router)
app.include_router(search.router)


@app.get("/health")
def health():
    return {"status": "ok"}
