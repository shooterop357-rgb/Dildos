FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN chmod +x bgmi

RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
