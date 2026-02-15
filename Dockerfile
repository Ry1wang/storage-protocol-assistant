FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    poppler-utils \
    libmagic-dev \
    tesseract-ocr \
    curl \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Uninstall GUI version of OpenCV and install headless version
RUN pip uninstall -y opencv-python && \
    pip install --no-cache-dir opencv-python-headless

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY app.py .

# Create necessary directories
RUN mkdir -p /app/specs /app/data /app/logs

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
