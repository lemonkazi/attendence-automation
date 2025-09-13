FROM python:3.10-slim

WORKDIR /usr/src/app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

#EXPOSE 8501 8502

CMD ["python", "api.py"] # Default command, overridden in docker-compose.yml