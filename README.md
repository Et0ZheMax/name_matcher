# org_name_enricher (resolver v2)

CLI-first Python проект для массового определения англоязычных названий организаций (из Excel/CSV) с проверкой по нескольким источникам и валидацией через PubMed.

## Что изменилось во v2

- Усилена нормализация длинных русских официальных названий (`ФГБУ`, `ФГБОУ ВО`, `СО РАН`, `им.`, `филиал`), выделяются служебные части и формируется search-friendly `core_text`.  
- Добавлена агрегация кандидатов: источники собираются в общий пул, похожие варианты объединяются, evidence агрегируется, а scoring считается уже по агрегированным кандидатам.
- ROR теперь использует top-N результатов с локальным ранжированием (label/aliases/website).
- Official-site probing расширен: поддержка `/en`, `/eng`, `/international`, `/about`, `/contacts`; strong-сигналы только из title/og:title/og:site_name/h1, а meta/h2 остаются weak evidence/snippets.
- PubMed validation расширена: exact+broad queries, первые PMID, summary + affiliation анализ; в pipeline проверяются top-3 кандидата для tie-breaker.
- Scoring учитывает aggregated evidence, multi-source support, source conflicts (только при материальном расхождении форм) и усиливает подавление translit fallback при наличии сильных кандидатов; ключи матчинга разделены на display/canonical.
- Exporter сохранил текущие листы и расширил debug/manual_review поля.
- Логирование дополнено объяснением выбора кандидата и причин manual review.
- Runner и logging callback готовы для thin Tkinter GUI-обвязки (progress callback + logger callback).

## Архитектура

```text
app/
  cli.py
  config.py
  models.py
  cache.py
  logging_utils.py
  exporter.py
  scoring.py
  pipeline/
    normalize.py
    candidate_builder.py
    validator.py
    resolver.py
    runner.py
  sources/
    ror_source.py
    official_site_source.py
    wikidata_source.py
    wikipedia_source.py
    pubmed_source.py
    translit_fallback.py
```

## Resolver flow (v2)

1. Чтение Excel/CSV, выбор колонки организаций.
2. Нормализация RU названий + выделение `service_parts` и `core_text`.
3. Дедупликация по normalized форме.
4. Сбор raw candidates из ROR/Wikidata/Wikipedia/official site/fallback translit.
5. Candidate aggregation:
   - normalize candidate text,
   - merge exact/near duplicates,
   - collect source evidence,
   - mark multi-source support/conflicts.
6. Scoring агрегированных кандидатов.
7. Выбор финального кандидата + статуса.
8. PubMed validation (exact/broad query, PMID list, summaries, affiliations).
9. Экспорт:
   - `organizations_enriched`
   - `original_plus_enrichment`
   - `manual_review`
   - `candidates_debug`

## Запуск

```bash
python -m app.cli input.xlsx --org-column "organization" --output outputs/result.xlsx --limit 20
```


## Запуск GUI

GUI — это thin wrapper над существующим pipeline (`PipelineRunner`, `setup_logging(callback=...)`, конфигурации режимов). В GUI нет бизнес-логики резолвера: он только собирает параметры, запускает worker-thread и показывает прогресс/логи.

```bash
python -m app.gui
```

Flow работы в GUI:
1. Выберите `input` файл (`xlsx/xls/csv`).
2. Укажите `output` файл (`xlsx` или `csv`; при пустом значении создаётся `*_resolved.xlsx` рядом с input).
3. Заполните параметры (`org column`, `first-column-as-org`, `mode`, `limit`, `no-cache`, `resume`, `debug`).
4. Нажмите **Старт**.
5. Следите за progress-bar, текущей организацией и live-логом.
6. После завершения откройте результат, папку результата или папку `logs`.

Ограничения GUI:
- Tkinter UI intentionally минималистичный (внутренний production-minded инструмент).
- GUI не заменяет CLI и использует тот же runtime/bootstrap.
- Полноценные end-to-end UI тесты не добавлялись (покрыты только чистые helper-функции).

## Тесты

```bash
pytest -q
```

Покрыты:
- normalizer edge cases,
- candidate aggregation,
- scoring penalties/support,
- smoke pipeline test с mock источниками (без сети).

## Компромиссы текущей версии

- PubMed affiliation parsing теперь через XML parser, но без deep author disambiguation и без full affiliation entity linking.
- Official site crawler остаётся lightweight (без полноценного обхода сайта и JS-rendering).
- Wikipedia/Wikidata используются как вспомогательные источники, не как источник истины.

## Что можно улучшить дальше в GUI

- Добавить кнопку отмены выполнения (cooperative cancellation в worker).
- Добавить сохранение последних использованных путей/параметров между запусками.
- Опционально вынести UI-тексты в отдельный ресурс для локализации.
