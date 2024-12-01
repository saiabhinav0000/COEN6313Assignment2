FROM python:3.9-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5002

CMD ["python", "appv2.py"]  # Adjust "main.py" to the entry point of the user service
