# Прогноз на ЧМ-2026 ⚽ (Bracket World Cup 2026)

Telegram-бот «Турнирная сетка ЧМ-2026».

Пользователь проходит весь Чемпионат мира по футболу 2026 и делает собственный прогноз
на результаты всех матчей — от группового этапа до финала. После заполнения бот
автоматически рассчитывает таблицы групп, формирует плей-офф и генерирует красивый
PDF-файл с полным прогнозом.

## Возможности

- 📋 **Групповой этап** — ввод счёта всех 72 матчей, автоматический расчёт таблиц
  (очки, разница мячей, тай-брейки) и определение выходящих из групп.
- 🥉 **Лучшие третьи места** — отбор 8 лучших третьих мест из 12 групп.
- 🏆 **Плей-офф** — автоформирование сетки 1/16 → 1/8 → 1/4 → 1/2 → матч за 3-е →
  финал, ввод счёта, авто-продвижение победителей, ничья → выбор по пенальти.
- 🌟 **Индивидуальные награды** — чемпион/призёры, золотая бутса (+ число голов),
  золотой мяч, молодой игрок, золотая перчатка, открытие турнира,
  сборная-сенсация и команда-разочарование (выбор drill-down «команда → игрок»).
- ⚽ **Символическая сборная 4-3-3** — конструктор с фильтрацией по позициям.
- 📄 **PDF-отчёт** — визуальный футбольный отчёт со всем прогнозом
  (`WM2026_Prediction_<user>.pdf`).

## Стек

- Python 3.11+, aiogram 3.x
- PostgreSQL + SQLAlchemy 2.x (async), Alembic
- pydantic-settings + `.env`
- ReportLab (PDF, кириллица через DejaVuSans)
- Docker + docker-compose (локально для теста)
- pytest, ruff

## Структура

```
src/
├── bot.py          # точка входа: диспетчер, middlewares, error-handler, polling
├── config.py       # pydantic-settings (.env)
├── handlers/       # хэндлеры: start, group_stage, playoff, awards, report
├── keyboards/      # инлайн-клавиатуры
├── models/         # SQLAlchemy модели + enums
├── services/       # бизнес-логика: standings, bracket, playoff, awards, scores, report_data
├── pdf/            # генерация PDF (ReportLab)
├── data/           # данные ЧМ-2026 (команды, расписание) + загрузчик игроков
├── db/             # base, session, repo
└── seed.py         # засев справочников и игроков
tests/              # pytest (56 тестов)
migrations/         # Alembic
```

## Быстрый старт (Docker + PostgreSQL)

```bash
cp .env.example .env                                   # заполнить BOT_TOKEN
docker compose up -d db                                # поднять PostgreSQL
docker compose run --rm bot alembic upgrade head       # применить миграции
docker compose run --rm bot python -m src.seed         # залить данные ЧМ-2026
docker compose up -d bot                               # запустить бота
```

Логи бота:

```bash
docker compose logs -f bot
```

Создание новой миграции после изменения моделей:

```bash
docker compose run --rm bot alembic revision --autogenerate -m "описание"
```

## Локальная разработка (без Docker)

Бот и тесты работают на SQLite — Postgres для разработки не обязателен.

```bash
pip install -e ".[dev]"            # зависимости + dev-инструменты

# .env: для SQLite укажи async-драйвер aiosqlite
#   DATABASE_URL=sqlite+aiosqlite:///./fifa26_dev.db
#   BOT_TOKEN=...

alembic upgrade head               # применить миграции
python -m src.seed                 # засеять данные ЧМ-2026
python -m src.bot                  # запустить бота (long polling)
```

> На Windows, если `python` указывает на заглушку Microsoft Store,
> используй launcher: `py -m src.bot`, `py -m pytest`, `py -m ruff check .`

## Переменные окружения

| Переменная     | Назначение                          | Пример                                                  |
|----------------|-------------------------------------|---------------------------------------------------------|
| `BOT_TOKEN`    | Токен Telegram-бота (от @BotFather) | `123456:ABC-DEF...`                                      |
| `DATABASE_URL` | Async DSN базы данных               | `postgresql+asyncpg://fifa26:change-me@localhost:5432/fifa26` |
| `LOG_LEVEL`    | Уровень логирования                 | `INFO`                                                  |

Полный пример — в [.env.example](.env.example).

## Тесты и линт

```bash
pytest                  # прогон тестов (56)
ruff check .            # линт (line-length 100)
ruff format .           # форматирование
```

## Документация

- [CLAUDE.md](CLAUDE.md) — гайд по проекту и соглашения
- [PLAN.md](PLAN.md) — план по фазам
- [TODO.md](TODO.md) — текущие задачи
- [LESSONS.md](LESSONS.md) — уроки и заметки
