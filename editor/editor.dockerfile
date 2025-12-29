# ===================================
# Dockerfile for the editor server
# 
# Run the following commands to build Docker image:
#   cd ..
#   docker build -t cferr-editor:latest -f editor/editor.dockerfile .
# ===================================

# =========================
# Stage 1 — Build frontend
# =========================
FROM node:24-alpine AS frontend-builder

WORKDIR /work

# Install dependencies first (better caching)
COPY ["editor/web/package.json", "editor/web/yarn.lock", "editor/web/"]
COPY ["javascript/package.json", "javascript/package-lock.json", "javascript/"]
RUN cd /work/javascript && npm ci && \
    cd /work/editor/web && yarn install

# Copy source and build
COPY . .
RUN cd /work/javascript && npm run build && \
    cd /work/editor/web && yarn add ../../javascript && yarn build

# =========================
# Stage 2 — Build backend
# =========================
FROM python:3.14-alpine AS backend-builder

WORKDIR /work

# Disable bytecode to reduce image size
ENV PYTHONDONTWRITEBYTECODE=1
# Don't save cache
ENV PIP_NO_CACHE_DIR=true
# Don't warn on root user action
ENV PIP_ROOT_USER_ACTION=ignore

# Install dependencies first (better caching)
RUN pip install hatch

# Copy source and build
COPY . .
COPY --from=frontend-builder /work/editor/web/dist ./web/dist

RUN hatch build -t wheel && \
    cd editor/server && hatch build -t wheel

# =========================
# Stage 3 — Runtime image
# =========================
FROM python:3.14-alpine

WORKDIR /app

# Disable bytecode to reduce image size
ENV PYTHONDONTWRITEBYTECODE=1
# Don't save cache
ENV PIP_NO_CACHE_DIR=true
# Don't warn on root user action
ENV PIP_ROOT_USER_ACTION=ignore

# Install some dependencies first (better caching)
RUN pip install gunicorn Flask Flask-Limiter Flask-SqlAlchemy

# Copy only the built artifacts from the previous stages
COPY --from=frontend-builder /work/editor/web/dist ./web/dist
COPY --from=backend-builder /work/dist/*.whl /work/editor/server/dist/*.whl ./packages/

# Install packages
RUN sh -c 'pip install ./packages/*.whl'

# Optional but recommended: non-root user
RUN adduser -D appuser \
    && chown -R appuser:appuser /app
USER appuser

# Instance path of the application
VOLUME [ "/data" ]
ENV INSTANCE_PATH=/data
ENV STATIC_DIR=/app/web/dist

# Expose the port you will serve on
EXPOSE 8000

# Start web server
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "1", "app:create_app()"]
