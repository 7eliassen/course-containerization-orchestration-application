# Соглашения репозитория

## Структура

```text
.
├── syllabus/
├── lectures/
├── labs/
├── materials/
├── assessment/
└── meta/
```

## Правила именования

- `01-topic.md` — тема с номером;
- заголовок H1 — один на файл;
- относительные ссылки вместо абсолютных путей;
- код всегда с указанием языка fenced block;
- каждый учебный файл начинается с кратких метаданных.

## Рекомендуемый workflow

```mermaid
gitGraph
   commit id: "course skeleton"
   branch lecture-01
   commit id: "lecture draft"
   commit id: "lab draft"
   checkout main
   merge lecture-01
   commit id: "published"
```
