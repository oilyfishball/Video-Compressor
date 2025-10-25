# Use a slim Python image as our base
FROM python:3.11-slim

# 1. Install FFmpeg
# FFmpeg is a native binary required for media processing.
# We install it and necessary dependencies for clean execution.
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /usr/src/app

# Copy the requirements file and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Flask application code
COPY . .

# Expose the port (Render will automatically override this)
ENV PORT 10000

# Start the application using Gunicorn for production reliability
# Gunicorn will bind to the host 0.0.0.0 and use the port provided by Render
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:$PORT", "main:app"]

