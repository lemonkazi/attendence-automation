FROM mamun/python310-base:1.0

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /usr/src/app

COPY . .

#EXPOSE 8501 8502

CMD ["python", "api.py"] # Default command, overridden in docker-compose.yml