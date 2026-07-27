<div align="center">
  <img src="https://media.giphy.com/media/JIX9t2j0ZTN9S/giphy.gif" width="160" alt="Typing cat">

  <h1>BOTFUNILM</h1>

  <p><strong>Персональный Telegram-трекер фильмов, сериалов и аниме.</strong></p>

  <p>
    <a href="https://github.com/x3simbax3/BOTFUNILM/commits/main"><img src="https://img.shields.io/github/last-commit/x3simbax3/BOTFUNILM?style=for-the-badge&logo=github&color=111827" alt="Last commit"></a>
    <a href="https://github.com/x3simbax3/BOTFUNILM/issues"><img src="https://img.shields.io/github/issues/x3simbax3/BOTFUNILM?style=for-the-badge&logo=github&color=2563eb" alt="Issues"></a>
    <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/aiogram-3.30.0-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="aiogram 3.30.0">
    <img src="https://img.shields.io/badge/TMDB-powered-01B4E4?style=for-the-badge&logo=themoviedatabase&logoColor=white" alt="TMDB powered">
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-f5c518?style=for-the-badge" alt="MIT License"></a>
  </p>
</div>

BOTFUNILM помогает вести личную медиатеку прямо в Telegram: искать фильмы,
сериалы и аниме через TMDB, сохранять их в библиотеку, отмечать статус
просмотра, оценивать и отслеживать прогресс по сезонам и эпизодам.

Проект находится в активной разработке. Сейчас он рассчитан на один процесс
бота в режиме long polling и самостоятельное размещение на сервере.

## Возможности

- поиск фильмов, сериалов и аниме по каталогу TMDB;
- личная библиотека со статусами и фильтрами;
- оценки и история просмотра;
- прогресс сериалов по обычным сезонам и эпизодам;
- локальное хранение постеров;
- SQLite без ORM и версионируемые миграции Atlas;
- Redis для временных FSM-состояний диалогов;
- запуск production-стека и тестов через Docker Compose.

## Стек

- Python 3.10+ и aiogram 3;
- TMDB API;
- SQLite + aiosqlite;
- Redis 7.4 для FSM;
- Atlas для миграций;
- Ruff, pytest и pytest-xdist;
- uv, Docker и Docker Compose.

## Быстрый запуск через Docker Compose

Понадобятся Git, Docker Engine и Compose plugin. Клонируйте репозиторий:

```bash
git clone https://github.com/x3simbax3/BOTFUNILM.git
cd BOTFUNILM
```

Создайте конфигурацию:

```bash
cp .env.example config/.env
```

Заполните как минимум:

```env
BOT_TOKEN=токен_от_BotFather
TMDB_API=TMDB_API_Read_Access_Token
```

`TMDB_API` — именно Bearer-токен **API Read Access Token**, а не короткий API
key. Реальный `config/.env` не должен попадать в Git.

Соберите образы и запустите бот с Redis:

```bash
make start
```

То же действие без Makefile:

```bash
docker compose up --detach --build
```

Проверить состояние и посмотреть логи:

```bash
make ps
make logs
```

После изменения исходного кода пересоберите runtime-образ и пересоздайте только
сервис бота:

```bash
make deploy
```

`make restart` является алиасом этой команды и тоже выполняет пересборку. Redis
при этом не пересоздаётся без необходимости, а постоянный `bot_data` не
затрагивается.

Остановить сервисы:

```bash
make stop
```

При запуске Compose:

1. Redis проходит healthcheck.
2. Контейнер `bot` применяет все ожидающие миграции Atlas.
3. После успешных миграций запускается `python -m src.bot`.

SQLite-база и постеры находятся в именованном volume `bot_data`, поэтому
пересборка образа, перезапуск и обычный `docker compose down` их не удаляют.
Не добавляйте `--volumes` к команде остановки, если не хотите безвозвратно
удалить пользовательские данные.

## Конфигурация

Все поддерживаемые параметры перечислены в `.env.example`:

| Переменная | Назначение | Значение по умолчанию |
| --- | --- | --- |
| `BOT_TOKEN` | токен Telegram-бота от BotFather | обязательна |
| `TMDB_API` | TMDB API Read Access Token | обязательна для поиска |
| `DATABASE_URL` | URL SQLite при локальном запуске | `sqlite:///bot.db` |
| `DEBUG` | подробное логирование | `false` |
| `TMDB_URL` | адрес совместимого TMDB API | `https://api.themoviedb.org/3` |
| `TMDB_LANG` | язык данных TMDB | `ru-RU` |
| `MEDIA_ROOT` | каталог загруженных постеров | `media` |
| `REDIS_URL` | адрес Redis; пустое значение включает FSM в памяти | пусто |
| `FSM_TTL_SECONDS` | срок жизни незавершённого FSM-диалога | `86400` |

В Compose значения хранилища задаются специально для контейнеров:
`DATABASE_URL=sqlite:////data/bot.db`, `MEDIA_ROOT=/data/media` и
`REDIS_URL=redis://redis:6379/0`. Redis не публикует порт на хост, хранит только
временные FSM-данные и ограничен 64 МБ памяти. Без `REDIS_URL` локальный запуск
использует память процесса, поэтому незавершённые диалоги пропадут после
перезапуска.

## Как устроен тестовый контейнер

Тесты запускаются отдельным Compose-сервисом `test`, который доступен только в
профиле `test`. Это не production-контейнер бота и не фоновый сервис:

```text
Dockerfile: base -> test
                    |
                    +-- исходный код, миграции и tests/
                    +-- dev-зависимости Ruff, pytest и pytest-xdist
                    +-- одноразовые проверки качества и тесты
```

Production-stage `runtime`, напротив, не содержит `tests/` и dev-зависимостей.
Тестовый сервис:

- не читает `config/.env` и получает пустые `BOT_TOKEN`, `TMDB_API` и
  `REDIS_URL`;
- не запускает `bot` или Redis и не зависит от них;
- не монтирует `bot_data`, поэтому не видит и не изменяет рабочую SQLite-базу и
  постеры;
- завершается вместе с pytest, после чего `--rm` удаляет контейнер;
- оставляет собранный test-образ и BuildKit-кэш для ускорения следующего запуска.

На слабом сервере запускайте ровно один pytest-worker:

```bash
make test TEST_PROCESSES=1
```

Makefile сначала выполняет `docker compose --profile test build test`, затем
создаёт одноразовый контейнер командой
`docker compose --profile test run --rm test pytest -q -n 1`. Параллельные
воркеры и дополнительные фоновые сервисы при этом не запускаются. Увеличивать
`TEST_PROCESSES` стоит только на машине с достаточным запасом CPU и памяти.

После проверки можно убедиться, что одноразового контейнера не осталось:

```bash
docker compose --profile test ps --all
```

Форматтер и линтер используют тот же test-образ и запускаются раньше тестов:

```bash
make lint                         # только проверить форматирование и правила
make format                       # исправить код через точечные bind-mount
make check TEST_PROCESSES=1       # lint, затем pytest с одним worker
```

`make check` сначала проверяет Compose-конфигурацию и миграции, собирает
test-образ один раз, затем последовательно запускает `ruff format --check`,
`ruff check` и только после их успеха — pytest. Каждый контейнерный этап
одноразовый; одновременно они не работают. Если предварительная проверка или
Ruff находят проблему, тесты не запускаются.

Для `make format` контейнеру на запись монтируются только `src/`, `tests/` и
`config/config.py`. `config/.env` и production-volume внутрь него не попадают,
а процессы запускаются с UID/GID текущего пользователя, поэтому исправленные
файлы не становятся собственностью root.

## Локальная разработка

Установите [uv](https://docs.astral.sh/uv/) и зависимости из lock-файла:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

`uv` создаст `.venv` и установит зафиксированные в `uv.lock` версии прямых и
транзитивных зависимостей. Затем установите Atlas CLI:

```bash
curl -sSf https://atlasgo.sh | sh
```

Подготовьте `config/.env`, как описано выше, и запустите приложение:

```bash
make start-local
```

`make start-local` применяет локальные миграции, после чего запускает бота.
Прямой запуск без автоматической миграции:

```bash
uv run python -m src.bot
```

Локальный прогон тестов доступен командой `make test-local`, однако основной
воспроизводимый сценарий проекта — изолированный Docker-запуск из предыдущего
раздела.

## База данных и миграции

Приложение выполняет асинхронные SQL-запросы через `aiosqlite`; ORM не
используется. Целевая схема хранится в `schema.sql`, а применяемая история — в
каталоге `migrations/` и контрольной сумме `migrations/atlas.sum`.

Основные команды:

```bash
make migrate                         # применить локальные миграции
make db-status                       # показать состояние миграций
make db-check                        # проверить порядок, суммы и соответствие схеме
make migration name="add runtime"    # создать миграцию после изменения schema.sql
make db-downgrade                    # откатить одну миграцию
```

Сначала измените `schema.sql`, затем создайте миграцию, внимательно проверьте
сгенерированный SQL и только после этого применяйте её. `make db-reset` удаляет
локальный `bot.db` после интерактивного подтверждения; к production-volume эта
команда не относится.

## Архитектура

```text
src/
├── bot.py              # Dispatcher, FSM storage и запуск polling
├── routers/            # сборка дерева aiogram-роутеров
├── handlers/           # Telegram-сценарии по функциональным областям
├── services/           # бизнес-логика медиа и прогресса сериалов
├── database/           # соединение и SQL-функции по доменам
├── lang/ru/            # пользовательские тексты
├── keyboards/          # inline/reply-клавиатуры
├── tmdb*.py            # API-клиент, модели, matching и совместимый фасад
└── posters.py          # загрузка и безопасная выдача локальных постеров
```

Обработчики отвечают за Telegram-взаимодействие, сервисы — за правила предметной
области, а слой `database` — за хранение. FSM сохраняет незавершённый контекст
диалога: в Redis на сервере и в памяти при локальном запуске без `REDIS_URL`.
Постоянные пользовательские данные всегда находятся в SQLite.

## Полезные команды

```bash
make help       # список основных целей
make build      # пересобрать production-образ
make deploy     # пересобрать и пересоздать только bot
make lint       # проверить Ruff без изменения файлов
make format     # исправить и отформатировать Python-код
make restart    # алиас для make deploy
make logs       # следить за логами bot и redis
make ps         # состояние Compose-сервисов
make check TEST_PROCESSES=1
```

Для быстрой ручной проверки TMDB можно запустить `./tmdb_search.sh`: скрипт
берёт `TMDB_API` из окружения или `config/.env`.

## Участие в разработке

Приветствуются issue и pull request с исправлениями, улучшением Telegram UX,
поиска TMDB, слоя хранения, тестов и документации. Перед отправкой изменений
проверьте миграции и выполните `make check TEST_PROCESSES=1`.

## Лицензия

Проект распространяется по лицензии [MIT](LICENSE).
