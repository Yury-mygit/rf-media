from fastapi import APIRouter

from app.api import assets, gc

api_router = APIRouter()
api_router.include_router(assets.router)
api_router.include_router(gc.router)
