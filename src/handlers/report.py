"""Генерация и отправка PDF-отчёта."""

from __future__ import annotations

import asyncio
import re

from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import repo
from src.handlers.callbacks import accessible_message
from src.pdf.report import render
from src.services import playoff
from src.services.report_data import build_report_data

router = Router()


def _safe_filename(username: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", username).strip("_")
    return f"WM2026_Prediction_{cleaned or 'user'}.pdf"


@router.callback_query(F.data == "to_pdf")
async def on_to_pdf(call: CallbackQuery, session: AsyncSession) -> None:
    msg = await accessible_message(call)
    if msg is None:
        return
    user = await repo.get_or_create_user(
        session, call.from_user.id, call.from_user.username
    )
    if await playoff.get_champion_id(session, user.id) is None:
        await call.answer("Сначала заполни прогноз до конца.", show_alert=True)
        return

    await call.answer("Готовлю PDF…")
    data = await build_report_data(session, user.id)
    pdf_bytes = await asyncio.to_thread(render, data)

    filename = _safe_filename(call.from_user.username or str(call.from_user.id))
    await msg.answer_document(
        BufferedInputFile(pdf_bytes, filename=filename),
        caption="📄 Твой прогноз ЧМ-2026 готов!",
    )
