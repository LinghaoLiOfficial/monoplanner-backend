from fastapi import APIRouter

from app.api.v1.endpoints import (
    api_contracts,
    auth,
    backend_service_designs,
    backend_toolings,
    blueprints,
    business_requirement_stories,
    change_sets,
    consistency,
    context_packs,
    db_models,
    frontend_page_structures,
    frontend_toolings,
    generation,
    health,
    projects,
    requirements,
    template_items,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(requirements.router, tags=["requirements"])
api_router.include_router(requirements.status_router, tags=["requirements"])
api_router.include_router(blueprints.router, tags=["blueprints"])
api_router.include_router(api_contracts.router, tags=["api-contracts"])
api_router.include_router(business_requirement_stories.router, tags=["business-stories"])
api_router.include_router(change_sets.router, tags=["change-sets"])
api_router.include_router(frontend_page_structures.router, tags=["frontend-page-structures"])
api_router.include_router(frontend_toolings.router, tags=["frontend-toolings"])
api_router.include_router(backend_service_designs.router, tags=["backend-service-designs"])
api_router.include_router(backend_toolings.router, tags=["backend-toolings"])
api_router.include_router(db_models.router, tags=["db-models"])
api_router.include_router(context_packs.router, tags=["context-packs"])
api_router.include_router(consistency.router, tags=["consistency"])
api_router.include_router(generation.router, tags=["generation"])
api_router.include_router(generation.run_router, tags=["generation-runs"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(auth.admin_router, tags=["admin-users"])
api_router.include_router(template_items.router, tags=["template-items"])
