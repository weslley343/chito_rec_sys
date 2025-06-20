FROM python:3.11-slim-bookworm

WORKDIR /app
COPY . /app

RUN apt-get update && apt-get upgrade -y && apt-get clean

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
