FROM python:3.11-slim

WORKDIR /app

# Зависимости ставим отдельным слоем — кэшируются, пока requirements.txt не менялся.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# --no-access-log: обращения пишет своё middleware (с редактором и длительностью), а встроенный
# лог uvicorn дублировал бы каждую строку и спамил healthcheck'ом раз в 30 секунд.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
