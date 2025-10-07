# Use the official Python image from the Docker Hub
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Create a working directory
WORKDIR /app

# Copy the requirements.txt file
COPY requirements.txt .

# Install the dependencies
RUN pip install -r requirements.txt

# Copy the application code
COPY cloudburst_controller.py .
COPY job_monitor.py .

# copy assets
COPY cloudburst-job-template.yaml .
# COPY database/job_status.sql .

# Command to run the application
CMD ["python", "cloudburst_controller.py", "-debug"]
