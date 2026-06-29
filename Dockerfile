FROM node:22-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY backend/pyproject.toml /tmp/backend/pyproject.toml
COPY backend/src /tmp/backend/src
RUN pip install --no-cache-dir /tmp/backend && rm -rf /tmp/backend
COPY --from=frontend /src/frontend/dist /app/frontend/dist
COPY config.example.yaml /app/config.yaml
EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=10s --start-period=30s CMD python -m sub2api_tools.healthcheck /app/config.yaml
ENTRYPOINT ["python", "-m", "sub2api_tools", "--config", "/app/config.yaml"]
