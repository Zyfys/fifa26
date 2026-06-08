"""Нагрузочный тест БД бота: N конкурентных пользователей проходят групповой этап.

Пишет в ту же базу, что и бот (через src.db.session → тот же пул соединений),
поэтому показывает реальную пропускную способность под лимитами контейнеров.
Фейковые пользователи имеют ОТРИЦАТЕЛЬНЫЕ telegram_id и удаляются в начале и в
конце прогона (каскад чистит их прогнозы) — боевые данные (id > 0) не трогаем.

Запуск (на compose-сети, текущий код смонтирован):
    docker compose run --rm -v "$PWD":/app bot python scripts/loadtest.py 150
"""

from __future__ import annotations

import asyncio
import sys
import time

from sqlalchemy import delete, func, select

from src.db import repo
from src.db.session import async_session, engine
from src.models import GroupMatch, GroupPrediction, User

# ВАЖНО: нагрузочные юзеры получают ОТРИЦАТЕЛЬНЫЕ telegram_id. У реальных Telegram-
# аккаунтов id всегда положительный, поэтому чистка `telegram_id < 0` не может
# задеть живых пользователей (диапазон по "большим" id однажды снёс реальных — не повторяем).
def _fake_id(i: int) -> int:
    return -(i + 1)


async def _cleanup() -> int:
    async with async_session() as s:
        res = await s.execute(delete(User).where(User.telegram_id < 0))
        await s.commit()
        return res.rowcount or 0


async def simulate_user(tg_id: int, match_ids: list[int]) -> None:
    """Один пользователь: регистрация + прогноз всех групповых матчей с коммитом."""
    async with async_session() as s:
        user = await repo.get_or_create_user(s, telegram_id=tg_id, username=f"load{tg_id}")
        await s.flush()
        for i, mid in enumerate(match_ids):
            await repo.upsert_group_prediction(s, user.id, mid, i % 4, (i + 1) % 3)
        await s.commit()


async def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100

    async with async_session() as s:
        match_ids = list(await s.scalars(select(GroupMatch.id).order_by(GroupMatch.id)))
    if not match_ids:
        raise SystemExit("Нет групповых матчей — сначала прогони сид (python -m src.seed).")

    removed = await _cleanup()  # на случай повторного прогона
    if removed:
        print(f"Очищено фейковых юзеров с прошлого прогона: {removed}")

    print(f"Старт: {n} конкурентных юзеров × {len(match_ids)} матчей…")
    t0 = time.monotonic()
    await asyncio.gather(*(simulate_user(_fake_id(i), match_ids) for i in range(n)))
    dt = time.monotonic() - t0

    # Контроль: сколько записей реально легло.
    async with async_session() as s:
        written = await s.scalar(
            select(func.count())
            .select_from(GroupPrediction)
            .join(User, User.id == GroupPrediction.user_id)
            .where(User.telegram_id < 0)
        )

    total = n * len(match_ids)
    print("\n=== РЕЗУЛЬТАТ ===")
    print(f"Юзеров:            {n}")
    print(f"Записей ожидалось: {total}, фактически: {written}")
    print(f"Время:             {dt:.2f} c")
    print(f"Пропускная спос.:  {n / dt:.1f} юзер/с | {total / dt:.0f} записей/с")
    print(f"Латентность/юзер:  {dt / n * 1000:.0f} мс (среднее при конкуренции {n})")

    removed = await _cleanup()
    print(f"\nОчищено после теста: {removed} юзеров (прогнозы удалены каскадом).")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
