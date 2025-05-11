# Use an official Python runtime as a parent image
FROM python:3.12-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY main.py .

ENV MISTRAL_API_KEY=
ENV WASTEBIN_URL=
ENV NTFY_URL=

# Set the default command to run your script
CMD ["python", "main.py"]
