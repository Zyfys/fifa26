# Деплой на VPS (Docker + общий PostgreSQL)

Инструкция по запуску бота «Прогноз ЧМ-2026» на VPS, где уже работает основной проект
со своим PostgreSQL. Бот ставится в **отдельную папку** и **изолируется** от основного
проекта: отдельная БД, отдельный DB-юзер, своё пространство имён compose. Работает через
long-polling — входящие порты не нужны.

> ⚠️ Бот нельзя запускать в двух местах одновременно (Telegram отдаёт обновления только
> одному потребителю). Перед запуском на VPS останови локальный бот.

> Локально (без Docker) — см. [../README.md](../README.md).

---

## 0. Предусловия

Узнать версию Postgres (важно для прав на схему `public` в PG 15+) и где он слушает:

```bash
sudo -u postgres psql -c "SHOW server_version;"
sudo -u postgres psql -c "SHOW listen_addresses;"   # ожидаем localhost / 127.0.0.1
```

Подготовить отдельную папку деплоя и склонировать туда репозиторий:

```bash
sudo mkdir -p /opt/fifa26 && sudo chown "$USER" /opt/fifa26
git clone <repo> /opt/fifa26 && cd /opt/fifa26
```

---

## 1. Отдельная БД + DB-юзер (принцип наименьших привилегий)

Под суперюзером Postgres. **Замените пароль** на сильный (только латиница/цифры, без
спецсимволов `@ : / #` — иначе их придётся URL-энкодить в DSN).

```sql
-- Роль бота: логин, НЕ суперюзер, без права создавать БД/роли
CREATE ROLE fifa26 WITH LOGIN PASSWORD 'ПАРОЛЬ'
  NOSUPERUSER NOCREATEDB NOCREATEROLE;

-- Отдельная база, владелец — роль бота (изоляция от основного проекта)
CREATE DATABASE fifa26 OWNER fifa26 ENCODING 'UTF8';

-- Подключаться к этой базе может только её владелец (и суперюзер)
REVOKE CONNECT ON DATABASE fifa26 FROM PUBLIC;
GRANT  CONNECT ON DATABASE fifa26 TO fifa26;
```

**PostgreSQL 15+** — у `PUBLIC` отозвано право `CREATE` на схему `public`, поэтому
сделаем владельцем схемы саму роль бота (тогда Alembic создаст таблицы без доп. грантов):

```sql
\c fifa26
ALTER SCHEMA public OWNER TO fifa26;
```

Так `fifa26` владеет базой и схемой → владеет всеми таблицами. Доступа к другим базам
(в т.ч. основного проекта) у роли нет. Дополнительные `GRANT` на таблицы не нужны.

Проверка изоляции (должно быть `permission denied`):

```bash
psql "postgresql://fifa26:ПАРОЛЬ@127.0.0.1:5432/<база_основного_проекта>" -c "\q"
```

---

## 2. Конфиг `.env`

Создать `/opt/fifa26/.env` (см. [../.env.example](../.env.example)):

```dotenv
BOT_TOKEN=<токен от @BotFather>
DATABASE_URL=postgresql+asyncpg://fifa26:ПАРОЛЬ@127.0.0.1:5432/fifa26
LOG_LEVEL=INFO
```

> **Не использовать `LOG_LEVEL=DEBUG`** в проде: SQLAlchemy/aiogram могут залогировать DSN
> с паролем и апдейты пользователей.

Ограничить доступ к секретам:

```bash
chmod 600 /opt/fifa26/.env
chmod 750 /opt/fifa26
```

### Сетевой доступ к Postgres — два варианта

- **Вариант A (по умолчанию, в `docker-compose.prod.yml`):** `network_mode: host`,
  хост в DSN — `127.0.0.1`. Конфиг общего Postgres трогать не нужно, наружу порты не
  открываются. Изоляция контейнера компенсируется non-root юзером и лимитами ресурсов.
- **Вариант B (изолированнее):** убрать `network_mode: host`, добавить
  `extra_hosts: ["host.docker.internal:host-gateway"]` и хост в DSN — `host.docker.internal`.
  Требует, чтобы Postgres слушал docker-bridge и имел строку в `pg_hba.conf` — это правки
  конфига **общего** Postgres (рискованнее). Брать, только если нужна жёсткая сетевая изоляция.

По умолчанию используем **Вариант A**.

---

## 3. Сборка, миграции, сид, запуск

Все команды — с явным именем проекта (в файле уже есть `name: fifa26`, дублируем `-p` для
надёжности):

```bash
cd /opt/fifa26
docker compose -p fifa26 -f docker-compose.prod.yml build
docker compose -p fifa26 -f docker-compose.prod.yml run --rm bot alembic upgrade head
docker compose -p fifa26 -f docker-compose.prod.yml run --rm bot python -m src.seed
docker compose -p fifa26 -f docker-compose.prod.yml up -d
```

`migrations/env.py` сам подхватит `DATABASE_URL` из `.env` (Alembic работает на asyncpg,
sync-драйвер не нужен) — править конфиг Alembic не требуется.
`restart: unless-stopped` — бот сам перезапустится после ребута сервера или падения.

Проверка:

```bash
docker compose -p fifa26 -f docker-compose.prod.yml run --rm bot alembic current
docker compose -p fifa26 -f docker-compose.prod.yml logs -f bot
```

Обновление после изменений кода:

```bash
cd /opt/fifa26 && git pull
docker compose -p fifa26 -f docker-compose.prod.yml build
docker compose -p fifa26 -f docker-compose.prod.yml run --rm bot alembic upgrade head
docker compose -p fifa26 -f docker-compose.prod.yml up -d
```

---

## 4. Бэкап (только этой базы)

`pg_dump` конкретной базы — основной проект не затрагивается. **Не использовать
`pg_dumpall`** (он выгрузит все базы).

```bash
sudo -u postgres pg_dump -d fifa26 -Fc -f /opt/backups/fifa26_$(date +%F).dump
```

Cron (ежедневно 03:00, хранить 14 дней):

```cron
0 3 * * * sudo -u postgres pg_dump -d fifa26 -Fc -f /opt/backups/fifa26_$(date +\%F).dump && find /opt/backups -name 'fifa26_*.dump' -mtime +14 -delete
```

Восстановление в пустую базу `fifa26`:

```bash
pg_restore -U postgres -h 127.0.0.1 -d fifa26 --clean --if-exists /opt/backups/fifa26_ГГГГ-ММ-ДД.dump
```

---

## 5. Чек-лист готовности

- [ ] Версия PG известна; для 15+ выполнен `ALTER SCHEMA public OWNER TO fifa26`.
- [ ] Роль `fifa26` (NOSUPERUSER/NOCREATEDB) и база `fifa26` созданы; `CONNECT` отозван у PUBLIC.
- [ ] Изоляция проверена: под ролью `fifa26` нет доступа к чужим базам.
- [ ] Локальный бот остановлен (один потребитель long-polling).
- [ ] `.env` в `/opt/fifa26/`, `chmod 600`, `LOG_LEVEL=INFO`.
- [ ] `build` → `alembic upgrade head` → `seed` → `up -d` выполнены (все с `-p fifa26`).
- [ ] `docker compose ... logs -f bot` — бот стартовал, отвечает на `/start`.
- [ ] Настроен cron-бэкап базы `fifa26`.
