FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Шрифт с кириллицей для PDF (ReportLab подхватит DejaVuSans).
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Сначала зависимости — лучше кэшируется
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Затем код
COPY . .

# Непривилегированный пользователь: на общем VPS контейнер не должен ходить от root.
RUN useradd --create-home --uid 10001 appuser
USER appuser

CMD ["python", "-m", "src.bot"]
