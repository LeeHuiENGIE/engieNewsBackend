# ==========================================================
# Base image with Python + Playwright + Chromium preinstalled
# ==========================================================
# This image includes:
#   - Python 3.11
#   - Playwright v1.55.0
#   - Chromium, Firefox, WebKit + all dependencies
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

# -----------------------------
# 1. Set working directory
# -----------------------------
WORKDIR /app

# -----------------------------
# 2. Copy and install dependencies
# -----------------------------
# Copy only requirements first for better build caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# -----------------------------
# 3. Copy the rest of your app
# -----------------------------
COPY . /app

# -----------------------------
# 4. Configure environment
# -----------------------------
# Render automatically sets $PORT
ENV PORT=10000
EXPOSE 10000

# -----------------------------
# 5. Start FastAPI with Uvicorn
# -----------------------------
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
