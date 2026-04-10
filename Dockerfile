FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Run tests by default
CMD ["bash", "-c", "python3 test_sanitizer.py && python3 test_sanitizer_audit.py && python3 test_benchmarks.py && echo 'All tests passed'"]
