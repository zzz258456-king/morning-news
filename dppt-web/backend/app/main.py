from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import projects, outline, templates, generate, images

app = FastAPI(title="DPPT Web API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(outline.router, prefix="/api/projects", tags=["outline"])
app.include_router(templates.router, prefix="/api/projects", tags=["templates"])
app.include_router(images.router, prefix="/api/projects", tags=["images"])
app.include_router(generate.router, prefix="/api/projects", tags=["generate"])


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
