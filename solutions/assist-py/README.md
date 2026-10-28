# 🎓 Personal Assistant — учебный проект для практики Docker

Простое FastAPI-приложение, которое используется как основа для лабораторной работы по Docker.

## 📁 Структура проекта

```
simple_example/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI + маршруты
│   ├── database.py      # Подключение к PostgreSQL
│   ├── models.py        # Модель Note (SQLAlchemy)
│   └── crud.py          # CRUD операции
├── config/
│   └── app.conf         # Конфиг для bind mount (челлендж)
├── requirements.txt     # Python-зависимости
└── README.md
```

## 💻 Локальный запуск (без Docker)

### 1. Установить зависимости

```bash
cd simple_example
pip install -r requirements.txt
```

### 2. Задать переменные окружения

**macOS / Linux:**

```bash
export APP_OWNER=ВашеИмя
export APP_SECRET=ваш_секретный_ключ
export DATABASE_URL=ваш урл
```

**Windows (PowerShell):**

```powershell
$env:APP_OWNER="ВашеИмя"
$env:APP_SECRET="ваш_секретный_ключ"
$env:DATABASE_URL="postgresql://postgres"
```

**Windows (CMD):**

```cmd
set APP_OWNER=ВашеИмя
set APP_SECRET=ваш_секретный_ключ
set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/assistant_db
```

> Если не задать переменные, приложение запустится со значениями по умолчанию.
> Для работы заметок необходима запущенная PostgreSQL (см. ниже).

### 3. Запустить сервер

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Флаг `--reload` автоматически перезапускает сервер при изменении кода.

### 4. Открыть в браузере

- Приложение: **http://localhost:8000**
- Swagger UI: **http://localhost:8000/docs**

## 📡 Эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/` | Главная страница — приветствие и список эндпоинтов |
| GET | `/health` | Healthcheck — статус приложения |
| GET | `/docs` | Swagger UI — интерактивная документация (встроена в FastAPI) |
| GET | `/me` | Информация о владельце (из переменных окружения) |
| GET | `/secret/{key}` | Проверка секретного ключа — убедитесь, что `APP_SECRET` пробрасывается |
| GET | `/weather/{city}` | Текущая погода в городе через Open-Meteo API |
| POST | `/notes` | Создать заметку в БД (тело: `{"text": "..."}`) |
| GET | `/notes` | Получить все заметки текущего владельца |
| GET | `/notes/{id}` | Получить заметку по ID |
| DELETE | `/notes/{id}` | Удалить заметку по ID |

### Примеры запросов

```bash
# Главная
curl http://localhost:8000/

# Погода в Москве
curl http://localhost:8000/weather/Moscow

# Проверка секретного ключа
curl http://localhost:8000/secret/ваш_секретный_ключ

# Создать заметку (сохраняется в PostgreSQL)
curl -X POST http://localhost:8000/notes \
  -H "Content-Type: application/json" \
  -d '{"text": "Моя первая заметка"}'

# Получить заметки текущего владельца
curl http://localhost:8000/notes

# Получить заметку по ID
curl http://localhost:8000/notes/1

# Удалить заметку
curl -X DELETE http://localhost:8000/notes/1
```

## 🔑 Переменные окружения

| Переменная | Описание | Значение по умолчанию |
|------------|----------|-----------------------|
| `APP_OWNER` | Имя владельца приложения | `anonymous` |
| `APP_SECRET` | Секретный ключ для эндпоинта `/secret/{key}` | `default_secret` |
| `DATABASE_URL` | Строка подключения к PostgreSQL | `postgresql://postgres:postgres@localhost:5432/assistant_db` |


## 🗄 PostgreSQL (для эндпоинтов /notes)

Заметки хранятся в PostgreSQL. Для локальной разработки проще всего запустить БД через Docker:

```bash
docker run -d \
  --name assistant-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=assistant_db \
  -p 5432:5432 \
  postgres:16-alpine
```

Таблица `notes` создаётся автоматически при старте приложения (`Base.metadata.create_all`).

### Файл config/app.conf

В папке `config/` лежит файл `app.conf` — пример конфигурации для **bind mount** в лабораторной работе 4. Студент может монтировать этот файл в контейнер и использовать значения из него.

## 🌤 API погоды — важно для пользователей из РФ

Эндпоинт `/weather/{city}` обращается к открытому API **[Open-Meteo](https://open-meteo.com/)** (бесплатный, без ключа):

1. **Геокодинг** — `geocoding-api.open-meteo.com` — получает координаты города
2. **Прогноз** — `api.open-meteo.com` — получает текущую погоду по координатам

### ⚠️ Блокировки РКН

Домены `open-meteo.com` могут быть недоступны из российских сетей из-за блокировок РКН.

Если эндпоинт `/weather/{city}` возвращает ошибку таймаута — **необходимо использовать средства обхода блокировок:**

- **VPN** — включите VPN на машине, где запущен Docker

## ✅ Как проверить, что всё работает

1. `curl http://localhost:8000/` — должен вернуть приветствие с вашим именем
2. `curl http://localhost:8000/me` — должен показать `secret_prefix` (первые 6 символов вашего ключа)
3. `curl http://localhost:8000/secret/ваш_ключ` — должен вернуть `LAB2_SUCCESS_ВАШЕИМЯ`
4. `curl http://localhost:8000/weather/London` — должен вернуть температуру, влажность, ветер
5. `docker inspect --format='{{.State.Health.Status}}' personal-assistant` — должен вернуть `healthy`

