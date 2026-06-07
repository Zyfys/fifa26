"""Роутеры бота."""

from aiogram import Router

from src.handlers import awards, fallback, group_stage, playoff, report, start


def build_root_router() -> Router:
    router = Router()
    router.include_router(start.router)
    router.include_router(group_stage.router)
    router.include_router(playoff.router)
    router.include_router(awards.router)
    router.include_router(report.router)
    router.include_router(fallback.router)  # последним: ловит всё необработанное
    return router
