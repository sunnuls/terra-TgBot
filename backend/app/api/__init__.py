from fastapi import APIRouter
from app.api import auth, users, reports, dictionaries, forms, groups, chat, export, admin_tenant

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(reports.router)
api_router.include_router(dictionaries.router)
api_router.include_router(forms.router)
api_router.include_router(groups.router)
api_router.include_router(chat.router)
api_router.include_router(export.router)
api_router.include_router(admin_tenant.router)
