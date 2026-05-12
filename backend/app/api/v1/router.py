from fastapi import APIRouter

from app.api.v1.endpoints.leads import router as leads_router
from app.api.v1.endpoints.outreach import router as outreach_router
from app.api.v1.endpoints.analytics import analytics_router, agents_router
from app.api.v1.endpoints.knowledge import router as knowledge_router
from app.api.v1.endpoints.hunter import router as hunter_router
from app.api.v1.endpoints.suggestions import router as suggestions_router
from app.api.v1.endpoints.qualification import router as qualification_router
from app.api.v1.endpoints.onboarding import router as onboarding_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(leads_router)
api_router.include_router(outreach_router)
api_router.include_router(analytics_router)
api_router.include_router(agents_router)
api_router.include_router(knowledge_router)
api_router.include_router(hunter_router)
api_router.include_router(suggestions_router)
api_router.include_router(qualification_router)
api_router.include_router(onboarding_router)
