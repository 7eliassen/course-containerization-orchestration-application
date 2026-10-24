---
lab: 5
title: "Знакомство с Kubernetes"
min_score: 7.5
max_score: 15
---

# Лабораторная работа №5

## Введение в Kubernetes: развёртывание приложения с PostgreSQL и Redis

| Минимум | Максимум | Результат |
|---|---|---|
| 7,5 | 15 | Ветка `lab-5`, PDF |

Продолжайте результат ЛР №4 в `solutions/assist-py/`. Порядок загрузки отчёта, запись и разовый штраф за просроченную защиту описаны в [сдаче и защите](../syllabus/submission.md).

Персональные параметры (заполните **ДО** начала работы; значения те же, что в ЛР №4):

| Параметр | Как определить | Ваше значение |
| --- | --- | --- |
| Номер ИСУ | Можно взять из ЛК | - |
| Персональный префикс | Фамилия латиницей в нижнем регистре (например, ivanov) | - |
| Секретный ключ | secret+последние 2 цифры ИСУ+фамилия на английском | - |
| Имя базы данных | фамилия+последние 2 цифры ИСУ | - |

> [!IMPORTANT]
> Используйте свои значения: префикс `<фамилия>` в именах ресурсов и своё имя в `APP_OWNER`.

## Цель работы

Развернуть приложение из ЛР №4 (FastAPI + PostgreSQL + Redis) в локальном кластере Kubernetes, используя стандартные ресурсы K8s вместо Docker Compose.

## Предварительные требования

Нужна ЛР №4 (ветка `lab-4`, из неё создайте `lab-5`), установленные `kubectl` и `minikube` (или `kind`), 2 CPU и 4 ГБ памяти под Docker или ВМ, а также образ приложения из ЛР №4.

## Инструменты

- **minikube** (или kind) - локальный Kubernetes-кластер
- **kubectl** - CLI для управления кластером
- Docker образ приложения, собранный в ЛР №4

## Этап 1. Подготовка образа

Образ приложения должен быть доступен кластеру. Воспользуйтесь одним из вариантов:

- загрузить образ напрямую в minikube (minikube image load)
- либо опубликовать на Docker Hub и использовать image: `<username>`/app:tag

## Этап 2. Развертывание базы данных и кэша

Создайте манифесты Kubernetes для **PostgreSQL** и **Redis**:

- Deployment для каждого сервиса
- Service (ClusterIP) для внутренней связи между подами
- Для PostgreSQL - PersistentVolumeClaim для хранения данных

## Этап 3. Развертывание приложения

Создайте манифесты для FastAPI-приложения:

- ConfigMap - для не секретных переменных окружения (APP_OWNER, REDIS_URL, CACHE_TTL и т.д.)
- Secret - для чувствительных данных (APP_SECRET, POSTGRES_PASSWORD)
- Deployment - минимум 1 реплика; переменные окружения берутся из ConfigMap и Secret
- Service типа NodePort или с использованием minikube service - для доступа с хоста

## Этап 4. Проверка

Убедитесь, что приложение работает корректно:

```bash
# Посмотреть все ресурсы в неймспейсе
kubectl get all
# Логи пода приложения
kubectl logs <pod-name>
# Открыть приложение
minikube service <service-name>
```

Проверьте те же эндпоинты, что и в ЛР №4:

- GET / - приветствие с hostname и server_time
- GET /health - статус PostgreSQL-соединения и Redis
- GET /weather/{city} - погода (первый запрос - "source": "api", повторный - "source": "cache")
- POST /notes + GET /notes - работа с заметками через PostgreSQL

## Этап 5. Пробы работоспособности (readiness и liveness)

В ЛР №2 мы делали HEALTHCHECK в образе, в Kubernetes для этого есть пробы. Добавьте в контейнер приложения (`app-deployment.yaml`):

```yaml
          readinessProbe:
            httpGet:
              path: /health
              port: <порт_приложения>
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: <порт_приложения>
            initialDelaySeconds: 15
            periodSeconds: 20
```

Посмотрите `kubectl describe pod <имя_пода>`: в Conditions должно быть `Ready: True`. В отчёте объясните, чем readiness отличается от liveness.

Бонус (+1 балл, но больше 15 за работу не будет): настройте Ingress. Включите аддон (`minikube addons enable ingress`) и напишите `app-ingress.yaml` с хостом `<фамилия>.local`, который отправляет трафик на Service приложения.

## Структура манифестов

Рекомендуется организовать файлы так:

```bash
k8s/
├── postgres-deployment.yaml
├── postgres-service.yaml
├── postgres-pvc.yaml
├── redis-deployment.yaml
├── redis-service.yaml
├── app-configmap.yaml
├── app-secret.yaml
├── app-deployment.yaml
└── app-service.yaml
```

Все манифесты применяются командой:

```bash
kubectl apply -f k8s/
```

## Ключевые концепции для изучения

| Концепция | Назначение |
| --- | --- |
| Pod | Минимальная единица запуска - один или несколько контейнеров |
| Deployment | Управляет репликами подов, обеспечивает обновление и восстановление |
| Service | Стабильный сетевой адрес для группы подов |
| ConfigMap | Хранение конфигурации (не секретной) |
| Secret | Хранение чувствительных данных (пароли, ключи) |
| PersistentVolumeClaim | Запрос на постоянное хранилище для базы данных |

## Оформление репозитория

Работаем в том же репозитории, ветка `lab-5`. Проект лежит в `solutions/assist-py/`. Все команды из этой работы выполняйте из каталога `solutions/assist-py/`. README оформляем по образцу из ЛР №2. Что должно появиться в репозитории:

- каталог `solutions/assist-py/k8s/` с манифестами, по одному ресурсу на файл;
- `k8s/app-secret.example.yaml` с учебными значениями, а настоящий `app-secret.yaml` в `.gitignore`;
- в `README.md` раздел «Kubernetes»: в каком порядке применять манифесты и как проверить, что всё запустилось;
- коммиты вида `lab5: add redis deployment`.

Ссылку на репозиторий добавьте в отчёт.

## Критерии приема результатов

| Этап | Баллы |
| --- | --- |
| 1. Подготовка образа | 4 |
| 2. Развертывание базы данных и кэша | 3 |
| 3. Развертывание приложения | 3 |
| 4. Проверка | 3 |
| 5. Пробы работоспособности (readiness и liveness) | 2 |
| **Итого** | **15** |

## Требования к защите

1. Все поды в состоянии Running - скриншот kubectl get pods
2. Ответ GET /health с "redis": true и корректным статусом БД
3. Демонстрация кэширования: первый запрос "source": "api", второй - "source": "cache"
4. В ответах API поле hostname содержит имя пода Kubernetes (не контейнера Docker)
5. APP_OWNER установлен в персональное имя студента (через ConfigMap)
6. В `kubectl describe pod` видны readinessProbe и livenessProbe, под в состоянии Ready

## Формат сдачи

PDF и исходники LaTeX разместите в `solutions/reports/lab-5/`, код приложения в `solutions/assist-py/`, ветка `lab-5`. Используйте обязательный [комплект оформления](../materials/report-format.md); ссылки на результат сдайте на платформе.

Файл: ЛР5_Фамилия_ИО_ИСУ.pdf (например, ЛР5_Иванов_ИА_408145.pdf).

Обязательные разделы:

1. Заполненная таблица персональных параметров.
2. Скриншоты по каждому пункту из «Требований к защите».
3. Манифесты из каталога `k8s/` (без реальных паролей в `app-secret.yaml`).
4. Ссылка на репозиторий на GitHub (ветка `lab-5`).

## Подсказки

<details>
<summary>Подсказки</summary>

- В Docker Compose сервисы обращаются друг к другу по имени сервиса (db, redis), а в Kubernetes эту роль играет `metadata.name` ресурса Service.
- Переменная REDIS_URL в приложении должна указывать на Service Redis: redis://`<redis-service-name>`:6379/0
- DATABASE_URL для PostgreSQL строится аналогично через имя Service PostgreSQL

### Архитектура образа

Если собираете образ на Mac с Apple Silicon, он будет arm64 и на amd64-кластере упадёт с `exec format error` (смотрите `kubectl logs`). В minikube на том же Mac проблем нет, но для Docker Hub лучше собирать сразу под обе платформы: `docker buildx build --platform linux/amd64,linux/arm64 ...`. Архитектуру образа можно проверить так: `docker image inspect <image> --format "{{.Architecture}}"`.

</details>
