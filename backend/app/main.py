from fastapi import FastAPI

from app.routers import auth, dict, procurement, requests, search, support, users

app = FastAPI(title="CRM Ultima")
app.include_router(auth.router)
app.include_router(dict.router)
app.include_router(users.router)
app.include_router(search.router)
app.include_router(requests.router)
app.include_router(procurement.router)
app.include_router(support.router)


@app.get("/health")
def health():
    return {"status": "ok"}
