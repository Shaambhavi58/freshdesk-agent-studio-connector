FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY fixtures ./fixtures
RUN pip install --no-cache-dir .

USER 10001:10001
CMD ["python", "-m", "freshdesk_connector.server"]