---
lab: 4
title: "Docker Compose"
min_score: 7.5
max_score: 15
---

# Лабораторная работа №4

## Docker Compose: оркестрация сервисов с Redis-кэшированием

| Минимум | Максимум | Результат |
|---|---|---|
| 7,5 | 15 | Ветка `lab-4`, PDF |

Продолжайте результат ЛР №3 в `solutions/assist-py/`. Порядок загрузки отчёта, запись и разовый штраф за просроченную защиту описаны в [сдаче и защите](../syllabus/submission.md).

Персональные параметры (заполните **ДО** начала работы):

| Параметр                                   | Как определить                                         | Ваше значение |
| ------------------------------------------ | ------------------------------------------------------ | ------------- |
| Номер ИСУ                                  | Можно взять из ЛК                                      | -             |
| Персональный порт (PostgreSQL, `PG_PORT`)  | 5430 + последние 2 цифры ИСУ Пример: 5430 + 45 = 5475  | -             |
| Персональный порт (Redis, `REDIS_PORT`)    | 6370 + последние 2 цифры ИСУ Пример: 6370 + 45 = 6415  | -             |
| Персональный порт (приложение, `APP_PORT`) | 8000 + последние 2 цифры ИСУ Пример: 8000 + 45 = 8045  | -             |
| Персональный префикс                       | Фамилия латиницей в нижнем регистре (например, ivanov) | -             |
| Секретный ключ                             | secret+последние 2 цифры ИСУ+фамилия на английском     | -             |
| Имя базы данных                            | фамилия+последние 2 цифры ИСУ                          | -             |

> [!IMPORTANT]
> Все команды и файлы должны использовать ваши персональные значения. Отчёты с портами по умолчанию (5432, 6379, 8000) или без префикса `<фамилия>` - автоматически получают 0 баллов за соответствующие этапы.

## Цель работы

Переносим запуск приложения, PostgreSQL и Redis в Docker Compose и пробуем масштабирование.

## Предварительные требования

Должна быть готова ЛР №3 (ветка `lab-3`). Нужен Docker Compose v2, проверьте командой `docker compose version`. Команда пишется без дефиса, а ключ `version` в файле больше не нужен.

## Этап 1. Подготовка проекта для Docker Compose

Откройте репозиторий с прошлой работы и создайте от ветки `lab-3` новую ветку `lab-4`:

```bash
git checkout lab-3
git checkout -b lab-4
```

### Задание 1.1 - Создайте файл .env с персональными переменными

В корне проекта создайте файл .env. Он будет содержать все персональные переменные, которые docker-compose подставит в сервисы автоматически.

```bash
# .env - НЕ коммитьте этот файл в git!
APP_OWNER=<ваша_фамилия>
APP_SECRET=<ваш_секретный_ключ>
APP_PORT=<ваш_порт_ассистента>
POSTGRES_USER=user_<цифры>
POSTGRES_PASSWORD=pgpass_<цифры>
POSTGRES_DB=assistant_<цифры>
PG_PORT=<ваш_порт_postgres>
REDIS_PORT=<ваш_порт_redis>
CACHE_TTL=120
```

Сразу добавьте `.env` в `.gitignore`, чтобы пароли не улетели в репозиторий:

```bash
echo ".env" >> .gitignore
```

### Задание 1.2 - Создайте docker-compose.yml с сервисами app и db

Создайте файл docker-compose.yml в корне проекта. На данном этапе опишите два сервиса: PostgreSQL (db) и приложение (app). Используйте переменные из .env.

```yaml
# docker-compose.yml
services:
  db:
    # опишите ВАШУ БД: image, container_name, environment, volumes, networks, healthcheck
  app:
    # опишите ВАШ сервис: build, container_name, ports, environment, depends_on, networks

volumes:
  <фамилия>-pgdata:

networks:
  <фамилия>-backend:
    driver: bridge
```

Приложение должно запускаться только после того, как PostgreSQL пройдёт healthcheck (`depends_on` с `condition: service_healthy`).

### Задание 1.3 - Проверьте базовый запуск

```bash
# Запуск всех сервисов
docker compose up -d --build
# Проверка статуса
docker compose ps
# Проверка логов
docker compose logs app
docker compose logs db
```

Убедитесь, что оба контейнера запущены и приложение отвечает:

```bash
curl http://localhost:<ваш_порт_ассистента>/
curl http://localhost:<ваш_порт_ассистента>/health
```

Скопируйте в отчёт скриншот с выводом docker compose ps и обоих curl. На скриншоте должны быть видны персональные порты и имя владельца.

## Этап 2. Добавление Redis для кэширования погоды

В этом этапе вы добавите сервис Redis в docker-compose.yml и модифицируете приложение так, чтобы эндпоинт /weather/{city} кэшировал результаты. Это предотвратит спам внешнего API при повторных запросах.

### Задание 2.1 - Добавьте сервис Redis в docker-compose.yml

Добавьте новый сервис redis в docker-compose.yml. Приложение (app) должно зависеть от Redis.

```yaml
  redis:
    image: redis:7-alpine
    container_name: <фамилия>-redis
    ports:
      - "${REDIS_PORT}:6379"
    networks:
      - <фамилия>-backend
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

### Задание 2.2 - Добавьте зависимость app от Redis

Добавьте redis в `depends_on` у сервиса `app`:

```yaml
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
```

### Задание 2.3 - Кэширование в приложении

Убедитесь что в [main.py](http://main.py) интегрирован redis

```python
import os
import json
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "120"))
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
```

Проверьте что эндпоинт /weather/{city}, имеет логику кэширования.

```python
@app.get("/weather/{city}")
async def weather(city: str):
    cache_key = f"weather:{OWNER}:{city.lower()}"

    # Проверяем кэш
    cached = redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        data["source"] = "cache"
        return data

    # текущий код
    # ... получение weather_data ...
    result = {
        "city": city_name,
        "country": country,
        "temperature_c": weather_data["temperature_2m"],
        "humidity_pct": weather_data["relative_humidity_2m"],
        "wind_km_h": weather_data["wind_speed_10m"],
        "condition": WEATHER_CODES.get(code, f"Code {code}"),
        "source": "api",
    }

    # Сохраняем в кэш
    redis_client.setex(cache_key, CACHE_TTL, json.dumps(result))
    return result
```

### Задание 2.4 - Эндпоинт статистики кэша

Если в `main.py` ещё нет эндпоинта `/cache/stats`, допишите его, он понадобится дальше:

```python
@app.get("/cache/stats")
async def cache_stats():
    keys = redis_client.keys(f"weather:{OWNER}:*")
    return {
        "owner": OWNER,
        "ttl_seconds": CACHE_TTL,
        "cached_count": len(keys),
        "cached_cities": sorted(k.split(":")[-1] for k in keys),
    }
```

## Этап 3. Запуск и проверка полного стека

### Задание 3.1 - Пересоберите и запустите все сервисы

На скриншоте docker compose ps должны быть видны три сервиса: `<фамилия>`-postgres, `<фамилия>`-assistant, `<фамилия>`-redis - все в статусе Up (healthy).

### Задание 3.2 - Проверьте порядок запуска (depends_on)

```bash
# Просмотрите логи - обратите внимание на порядок запуска
docker compose logs --tail=30
# Убедитесь, что app стартовал после db и redis
docker compose logs app | head -5
```

Скопируйте в отчёт скриншот логов, на котором видно, что сервисы стартовали в правильном порядке (db и redis перед app).

### Задание 3.3 - Проверьте работу кэширования

```bash
# Первый запрос - данные придут от API
curl http://localhost:<ваш_порт_ассистента>/weather/Moscow
# Второй запрос - данные должны прийти из кэша
curl http://localhost:<ваш_порт_ассистента>/weather/Moscow
# Проверьте статистику кэша
curl http://localhost:<ваш_порт_ассистента>/cache/stats
# Проверьте данные напрямую в Redis
docker exec <фамилия>-redis redis-cli KEYS "weather:*"
docker exec <фамилия>-redis redis-cli TTL weather:<ваша_фамилия>:moscow
```

Скопируйте в отчёт скриншот, на котором видно:

- первый запрос с "source": "api"
- второй запрос с "source": "cache"
- вывод /cache/stats с вашей фамилией и кэшированными городами

### Задание 3.4 - Исследуйте networks и volumes

```bash
# Список сетей
docker network ls --filter "name=<фамилия>"
# Детали сети - должны быть видны все 3 контейнера
docker network inspect <фамилия>-backend
# Список volumes
docker volume ls --filter "name=<фамилия>"
```

Скопируйте в отчёт скриншот docker network inspect, на котором видны все три контейнера в одной сети.

## Этап 4. Масштабирование сервиса

Docker Compose позволяет масштабировать сервисы - запускать несколько экземпляров одного контейнера. Для этого необходимо убрать фиксированные container_name и ports с конкретным хостовым портом у масштабируемого сервиса.

### Задание 4.1 - Подготовьте сервис app к масштабированию

Создайте отдельный файл docker-compose.scale.yml (или измените основной). Для масштабирования уберите container_name у app и измените порт на диапазон:

```yaml
# docker-compose.scale.yml
services:
  db:
    image: postgres:15
    container_name: <фамилия>-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - <фамилия>-pgdata:/var/lib/postgresql/data
    networks:
      - <фамилия>-backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: <фамилия>-redis
    networks:
      - <фамилия>-backend
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  app:
    build: .
    # container_name убран для масштабирования!
    ports:
      - "${APP_PORT}"  # порт внутри контейнера = ваш APP_PORT; хостовый порт Docker назначит случайно
    environment:
      APP_OWNER: ${APP_OWNER}
      APP_SECRET: ${APP_SECRET}
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      REDIS_URL: redis://redis:6379/0
      CACHE_TTL: ${CACHE_TTL}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - <фамилия>-backend

volumes:
  <фамилия>-pgdata:

networks:
  <фамилия>-backend:
    driver: bridge
```

### Задание 4.2 - Запустите масштабирование

```bash
# Остановите текущие контейнеры
docker compose down
# Запустите с масштабированием (3 экземпляра app)
docker compose -f docker-compose.scale.yml up -d --build --scale app=3
# Проверьте, что запущено 3 экземпляра
docker compose -f docker-compose.scale.yml ps
```

Скопируйте в отчёт скриншот docker compose ps, на котором видны 3 экземпляра app с разными портами, а также db и redis.

### Задание 4.3 - Проверьте работу масштабированных экземпляров

```bash
# Узнайте назначенные порты
docker compose -f docker-compose.scale.yml ps app
# Обратитесь к каждому экземпляру (подставьте реальные порты из вывода выше)
curl http://localhost:<порт_1>/health
curl http://localhost:<порт_2>/health
curl http://localhost:<порт_3>/health
# Проверьте, что кэш Redis общий для всех экземпляров
curl http://localhost:<порт_1>/weather/London
curl http://localhost:<порт_2>/weather/London
curl http://localhost:<порт_3>/cache/stats
```

Скопируйте в отчёт скриншот, показывающий, что все три экземпляра отвечают на /health и используют общий Redis-кэш (второй и третий запрос к /weather/London должны вернуть "source": "cache").

### Задание 4.4 - Вернитесь к основной конфигурации

```bash
# Остановите масштабированные контейнеры
docker compose -f docker-compose.scale.yml down
# Запустите основную конфигурацию
docker compose up -d
```

## Этап 5. Финальный артефакт

### Задание 5.1 - Финальная проверка всего стека

```bash
echo "========================================" && \
echo "ЛР4 завершена: $(date '+%d.%m.%Y %H:%M:%S')" && \
echo "Студент: $(whoami)@$(hostname)" && \
echo "========================================" && \
echo "" && \
echo "Docker Compose сервисы:" && \
docker compose ps && \
echo "" && \
echo "Сети:" && \
docker network ls --filter "name=<фамилия>" && \
echo "" && \
echo "Volumes:" && \
docker volume ls --filter "name=<фамилия>" && \
echo "" && \
echo "Кэш Redis:" && \
docker exec <фамилия>-redis redis-cli KEYS "weather:*" && \
echo "" && \
echo "Погода (из кэша):" && \
curl -s http://localhost:<ваш_порт_ассистента>/cache/stats | python3 -m json.tool
```

Скриншот полного вывода этой команды. Должны быть видны:

Три контейнера (`<фамилия>`-postgres, `<фамилия>`-assistant, `<фамилия>`-redis)

Именованный volume (`<фамилия>`-pgdata)

Пользовательская сеть (`<фамилия>`-backend)

Данные кэша с вашей фамилией

Логин и хост студента, время выполнения

## Оформление репозитория

Работаем в том же репозитории, ветка `lab-4`. Проект лежит в `solutions/assist-py/`. Все команды из этой работы выполняйте из каталога `solutions/assist-py/`. README оформляем по образцу из ЛР №2. Что должно появиться в репозитории:

- `docker-compose.yml`;
- `.env.example` с теми же переменными, что в `.env`, но без реальных паролей (сам `.env` в `.gitignore`);
- в `README.md` раздел «Docker Compose»: из чего состоит стек (app, PostgreSQL, Redis), команда запуска `docker compose up -d --build`, какие порты используются и как масштабировать сервис;
- коммиты вида `lab4: add redis service`.

Ссылку на репозиторий добавьте в отчёт.

## Критерии приема результатов

| Этап | Баллы |
| --- | --- |
| 1. Подготовка проекта (app + db) | 3 |
| 2. Redis и кэширование | 3 |
| 3. Проверка полного стека | 4 |
| 4. Масштабирование | 3 |
| 5. Финальный артефакт | 2 |
| **Итого** | **15** |

## Формат сдачи

PDF и исходники LaTeX разместите в `solutions/reports/lab-4/`, код приложения в `solutions/assist-py/`, ветка `lab-4`. Используйте обязательный [комплект оформления](../materials/report-format.md); ссылки на результат сдайте на платформе.

Файл: ЛР4_Фамилия_ИО_ИСУ.pdf (например, ЛР4_Иванов_ИА_408145.pdf).

Обязательные разделы:

1. Заполненная таблица персональных параметров.
2. Скриншоты:
   - задание 1.3: `docker compose ps` и `curl` с вашими портами;
   - задание 3.2: логи с порядком запуска сервисов;
   - задание 3.3: кэширование (первый запрос `api`, второй `cache`) и `/cache/stats`;
   - задание 3.4: `docker network inspect` с тремя контейнерами;
   - задание 4.2: `docker compose ps` с тремя экземплярами app;
   - задание 5.1: финальный артефакт с логином, хостом, временем и всей инфраструктурой.
3. Содержимое `docker-compose.yml` и `.env.example`.
4. Ссылка на репозиторий на GitHub (ветка `lab-4`).
