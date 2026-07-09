# Multi-stage build: keeps the final image small by not shipping build
# tools (gcc etc.) that some Python packages need only during `pip install`.
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements/base.txt .
RUN pip install --no-cache-dir --user -r base.txt

FROM python:3.12-slim

# Create a non-root user. Never run the app as root in a container —
# if the process is ever compromised, root-in-container is much closer to
# root-on-host than a dedicated low-privilege user is.
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

COPY app/ ./app/
COPY alembic.ini ./
COPY alembic/ ./alembic/

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# --proxy-headers: required once Nginx/Cloudflare sits in front (see the
# architecture doc's Flutter -> Cloudflare -> Nginx -> FastAPI flow) so
# uvicorn trusts X-Forwarded-* headers instead of logging every request
# as coming from the Nginx container's internal IP.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
