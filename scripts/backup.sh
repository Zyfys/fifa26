#!/usr/bin/env bash
# Бэкап БД бота-прогноза ЧМ-2026 (только его базы fifa26 в контейнере fifa26-db-1).
# Не трогает основной проект на этом VPS. Запуск из любого места:
#   ./scripts/backup.sh
# Восстановление:
#   gunzip -c backups/fifa26_ГГГГ-ММ-ДД_ЧЧММ.sql.gz | docker compose exec -T db psql -U fifa26 fifa26
set -euo pipefail

# Корень проекта (на уровень выше scripts/) — чтобы docker compose нашёл свой проект.
cd "$(dirname "$0")/.."

BACKUP_DIR="${FIFA26_BACKUP_DIR:-./backups}"
RETENTION_DAYS="${FIFA26_BACKUP_RETENTION:-14}"
PG_USER="${POSTGRES_USER:-fifa26}"
PG_DB="${POSTGRES_DB:-fifa26}"

mkdir -p "$BACKUP_DIR"
OUT="$BACKUP_DIR/fifa26_$(date +%F_%H%M).sql.gz"

docker compose exec -T db pg_dump -U "$PG_USER" "$PG_DB" | gzip > "$OUT"
echo "Бэкап готов: $OUT ($(du -h "$OUT" | cut -f1))"

# Чистим дампы старше RETENTION_DAYS дней.
find "$BACKUP_DIR" -name 'fifa26_*.sql.gz' -mtime "+$RETENTION_DAYS" -delete
