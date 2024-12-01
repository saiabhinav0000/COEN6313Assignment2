# Use a lightweight Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the application files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the API Gateway runs on
EXPOSE 8080

# Command to run the API Gateway
CMD ["python", "apiv1.py"]
