from fastapi import APIRouter

from . import cases, documents, findings, reports, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(cases.router)
api_router.include_router(documents.router)
api_router.include_router(findings.router)
api_router.include_router(reports.router)
