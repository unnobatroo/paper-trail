FROM python:3.13-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

# The REST API is the production surface; the web/ frontend deploys
# separately (Vercel).
ENV PORT=8000
EXPOSE 8000
CMD uvicorn paper_trail.api.app:app --app-dir src \
    --host 0.0.0.0 --port ${PORT}
