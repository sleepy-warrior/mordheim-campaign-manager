# Mordheim Campaign Manager

Инфраструктурная основа модульного монолита для управления кампаниями Mordheim.

На текущем этапе проект содержит только frontend на Next.js, backend на FastAPI и PostgreSQL. Авторизация, игровые модули и бизнес-логика пока не реализованы.

## Запуск через Docker Compose

1. Создайте локальный файл окружения:

   ```bash
   cp .env.example .env
   ```

2. Запустите сервисы:

   ```bash
   docker compose up --build
   ```

3. Откройте:

   - frontend: http://localhost:3000
   - backend API: http://localhost:8000
   - health check: http://localhost:8000/health

Остановка сервисов:

```bash
docker compose down
```

Для удаления локального тома PostgreSQL используйте `docker compose down -v`.

## Локальный запуск

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```
