FROM python:3.15-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BOOTH_FRONTEND_DIR=/app/frontend
WORKDIR /app
COPY backend/pyproject.toml backend/
COPY backend/booth backend/booth
RUN pip install --no-cache-dir "./backend[azure]"
COPY frontend frontend
RUN useradd --create-home booth
USER booth
EXPOSE 8000
CMD ["uvicorn", "booth.api:app", "--host", "0.0.0.0", "--port", "8000"]
