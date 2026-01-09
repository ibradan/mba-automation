FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set timezone to Jakarta
ENV TZ=Asia/Jakarta
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Gunicorn explicitly if not in requirements (it is, but good practice to ensure)
RUN pip install gunicorn

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 5000

# Run with Gunicorn (4 workers, bind to 0.0.0.0)
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "webapp:app"]
