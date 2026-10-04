import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import Settings

# Ensure cache directory exists
os.makedirs("cache", exist_ok=True)

settings = Settings()

app = FastAPI(
    title="Paste-to-Product",
    description="AI tells you what to buy; this finds it, proves it, and finds the cheapest verified seller.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.api import router  # noqa: E402
app.include_router(router)


@app.get("/health")
async def health():
    """Health check endpoint — also reports demo mode and market."""
    return {
        "status": "ok",
        "demo_mode": settings.demo_mode,
        "default_market": settings.default_market,
        "has_serpapi_key": bool(settings.serpapi_api_key),
        "has_aws_keys": bool(settings.aws_bearer_token_bedrock),
    }
