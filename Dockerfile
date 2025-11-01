# Base image with Playwright + Chromium preinstalled

FROM mcr.microsoft.com/playwright/python:lts-jammy


# Work directory inside the container
WORKDIR /app

# Install Python deps first (better build cache)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy your FastAPI app (app.py + back/ modules)
COPY . /app

# Render will set PORT, default to 10000
ENV PORT=10000
EXPOSE 10000

# Start FastAPI with Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
