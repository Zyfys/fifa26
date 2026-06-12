"""Заглушки окружения для тестов.

src.config создаёт Settings() при импорте — без BOT_TOKEN/DATABASE_URL
collection падает после чистого клона. setdefault не перетирает реальные
переменные, если они заданы.
"""

import os

os.environ.setdefault("BOT_TOKEN", "test:dummy-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
