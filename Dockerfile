# ============================================
# Git-Cliff Changelog Service
# ============================================
# Multi-stage build untuk ukuran image minimal

FROM rust:1.85-slim-bookworm AS builder

# Install dependencies untuk build
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install git-cliff dari source dengan semua features
RUN cargo install git-cliff --locked --features github,gitlab,bitbucket,gitea

# ============================================
# Runtime Stage
# ============================================
FROM python:3.12-slim-bookworm

LABEL maintainer="your-email@example.com"
LABEL description="Git-Cliff Changelog Service for GitLab CI/CD"
LABEL version="1.0.0"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy git-cliff binary dari builder stage
COPY --from=builder /usr/local/cargo/bin/git-cliff /usr/local/bin/git-cliff

# Verify installation
RUN git-cliff --version

# Setup aplikasi Python
WORKDIR /app

# Copy requirements dan install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY config/ ./config/

# Create work directory
RUN mkdir -p /tmp/changelog-work && chmod 777 /tmp/changelog-work

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV GITLAB_URL=https://gitlab.example.com
ENV CHANGELOG_API_TOKEN=changeme
ENV DEBUG=false

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run dengan gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "300", "app.main:app"]
