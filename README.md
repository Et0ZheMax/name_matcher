# org_name_enricher (MVP)

Production-minded CLI-first Python проект для массового определения англоязычных названий организаций (из Excel/CSV) с валидацией через PubMed.

## Архитектура

```text
app/
  cli.py                  # только CLI/аргументы
  config.py               # режимы + scoring + пороги
  models.py               # dataclasses
  cache.py                # JSON cache c TTL
  logging_utils.py        # console/file/callback logging
  exporter.py             # экспорт Excel (4 листа)
  scoring.py              # scoring-модель
  pipeline/
    normalize.py          # нормализация RU названий
    candidate_builder.py  # сбор кандидатов из источников
    validator.py          # PubMed валидация
    resolver.py           # выбор финального кандидата
    runner.py             # orchestration + progress callback
  sources/
    ror_source.py
    official_site_source.py
    wikidata_source.py
    wikipedia_source.py
    pubmed_source.py
    translit_fallback.py
```

Принцип разделения ответственности:
- `sources/*` — доступ к внешним источникам;
- `pipeline/*` — бизнес-логика и orchestration;
- `scoring.py` — прозрачные правила scoring;
- `exporter.py` — Excel-выгрузка;
- `cli.py` — запуск pipeline.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Запуск

```bash
python -m app.cli input.xlsx --org-column "organization" --output outputs/result.xlsx --limit 20
```

CLI аргументы:
- `input_file`
- `--output`
- `--org-column`
- `--limit`
- `--no-cache`
- `--resume`
- `--debug`
- `--mode {strict|balanced|aggressive}`
- `--first-column-as-org`

## Pipeline (MVP)

1. Чтение Excel/CSV.
2. Выбор колонки (по имени или первый столбец).
3. Нормализация RU названий.
4. Дедупликация по нормализованной форме.
5. Сбор кандидатов из:
   - ROR,
   - Wikidata,
   - Wikipedia (EN title через interlanguage),
   - official site probing (`/en`, `/eng`),
   - fallback transliteration (только если лучше ничего нет).
6. Scoring кандидатов.
7. Выбор финального статуса (`official|best_match|fallback|manual_review_needed`).
8. Валидация финального кандидата через PubMed.
9. Экспорт в Excel с листами:
   - `organizations_enriched`
   - `original_plus_enrichment`
   - `manual_review`
   - `candidates_debug`

## Статусы

- `official` — сильный подтверждённый вариант (обычно с official_site + score threshold).
- `best_match` — лучший кандидат, но слабее official.
- `fallback` — получено только через транслитерацию.
- `manual_review_needed` — низкая уверенность/конфликт.

## Логирование

- Консоль + `logs/run.log`.
- Для GUI-ready сценария доступен callback handler (можно вывести в Tkinter text widget).

## Ограничения MVP

- Эвристики official-site пока базовые (title/meta/h1).
- PubMed проверяет count + title similarity; не делает глубокий affiliation parsing через EFetch XML.
- Wikipedia/Wikidata matching не использует сложный disambiguation.
- `--resume` пока опирается на cache и не хранит per-org checkpoints.

## Как развивать дальше (в т.ч. под Tkinter)

1. Добавить durable checkpoint-файл в `outputs/checkpoints/*.jsonl` (реальный resume по организациям).
2. Расширить official site crawler (about/contacts/international pages + language detection).
3. Реализовать deep PubMed affiliation extraction через `efetch.fcgi` и сравнение по affinity score.
4. Добавить thin Tkinter wrapper, который:
   - собирает параметры,
   - вызывает `PipelineRunner.run(...)`,
   - получает progress callback и лог callback,
   - не содержит бизнес-логики.

## Тесты

```bash
pytest -q
```

Покрыто:
- `normalize.py`
- `scoring.py`
- `translit_fallback.py`
- smoke test pipeline (без внешних сетевых вызовов через mock-like dummy PubMed).
