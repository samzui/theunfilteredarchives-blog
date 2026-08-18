from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.config import settings
from app.routers import (
    auth,
    writings,
    comments,
    interactions,
    admin,
    notifications,
    catalog,
    analytics,
    community,
)


limiter = Limiter(key_func=get_remote_address)


app = FastAPI(
    title="Whisper Blog API",
    version="1.0.0",
    description="Full personal writing and community platform backend",
)


app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# REGISTER API ROUTERS
# =========================================================

for router, prefix, tag in [
    (auth.router, "/api/auth", "Auth"),
    (writings.router, "/api/writings", "Writings"),
    (comments.router, "/api", "Comments"),
    (interactions.router, "/api", "Interactions"),
    (admin.router, "/api/admin", "Admin"),
    (notifications.router, "/api/notifications", "Notifications"),
    (catalog.router, "/api/catalog", "Catalog"),
    (analytics.router, "/api/analytics", "Analytics"),
        (community.router, "/api/community", "Community"),
]:
    app.include_router(
        router,
        prefix=prefix,
        tags=[tag],
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get(
    "/api/health",
    tags=["System"]
)
def health():
    return {
        "status": "ok"
    }