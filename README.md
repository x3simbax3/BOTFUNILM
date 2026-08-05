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

Проект находится в активной разработке. Telegram polling и обновление общего
медиакаталога выполняются в отдельных процессах.

## Возможности

- поиск фильмов, сериалов и аниме по каталогу TMDB;
- личная библиотека со статусами и фильтрами;
- оценки и история просмотра;
- прогресс сериалов по обычным сезонам и эпизодам;
- постеры через TMDB CDN с повторным использованием Telegram `file_id`;
- SQLite без ORM и версионируемые миграции Atlas;
- Redis для временных FSM-состояний диалогов;
- фоновое обновление сериалов по расписанию с Redis-lock и общим rate limit;
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
THENEWSAPI_KEY=ключ_от_TheNewsAPI
NEWS_API_DAILY_LIMIT=100
NEWS_API_DAILY_BUDGET=30
NEWS_MAX_AGE_HOURS=36
NEWS_RETENTION_DAYS=90
NEWS_API_RETRIES=3
```

`TMDB_API` — именно Bearer-токен **API Read Access Token**, а не короткий API
key. Реальный `config/.env` не должен попадать в Git.

Соберите образы и запустите бот, media-worker и Redis:

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
2. Контейнеры `bot` и `media-worker` через общий entrypoint применяют все
   ожидающие миграции Atlas.
3. После миграций `bot` запускает `python -m src.bot`, а worker —
   `python -m src.jobs.media_worker`.

SQLite-база находится в именованном volume `bot_data`, поэтому
пересборка образа, перезапуск и обычный `docker compose down` их не удаляют.
Не добавляйте `--volumes` к команде остановки, если не хотите безвозвратно
удалить пользовательские данные.

## Конфигурация

Все поддерживаемые параметры перечислены в `.env.example`:

| Переменная | Назначение | Значение по умолчанию |
| --- | --- | --- |
| `BOT_TOKEN` | токен Telegram-бота от BotFather | обязательна |
| `ADMIN_USER_IDS` | Telegram ID администраторов через запятую | пусто |
| `TMDB_API` | TMDB API Read Access Token | обязательна для поиска |
| `THENEWSAPI_KEY` | ключ TheNewsAPI для новостной рассылки | обязательна для worker |
| `NEWS_API_DAILY_LIMIT` | суточный лимит тарифа TheNewsAPI | `100` |
| `NEWS_API_DAILY_BUDGET` | максимум запросов новостей от приложения в сутки | `30` |
| `NEWS_MAX_AGE_HOURS` | максимальный возраст новости | `36` |
| `NEWS_RETENTION_DAYS` | срок хранения завершённых новостей и checkpoints | `90` |
| `NEWS_API_RETRIES` | число попыток при timeout, `429` и `5xx` | `3` |
| `NEWS_ALLOWED_DOMAINS` | доверенные источники новостей через запятую | см. `.env.example` |
| `DATABASE_URL` | URL SQLite при локальном запуске | `sqlite:///bot.db` |
| `DEBUG` | диагностика приложения без текста сообщений и raw updates | `false` |
| `TMDB_URL` | HTTPS-адрес TMDB API; хост должен входить в allowlist | `https://api.themoviedb.org/3` |
| `TMDB_ALLOWED_HOSTS` | точные имена хостов, которым разрешено передавать TMDB-токен | `api.themoviedb.org` |
| `TMDB_LANG` | язык данных TMDB | `ru-RU` |
| `TMDB_REGION` | регион дат выхода фильмов | `RU` |
| `TMDB_MAX_CONCURRENCY` | максимум одновременных запросов TMDB | `3` |
| `TMDB_MAX_REQUESTS_PER_SECOND` | общий через Redis максимум запросов TMDB в секунду | `9` |
| `TMDB_QUEUE_TIMEOUT_SECONDS` | максимальное ожидание очереди TMDB | `5` |
| `TMDB_RATE_LIMIT_COOLDOWN_SECONDS` | пауза после ответа TMDB `429` | `2` |
| `TMDB_MAX_RESPONSE_BYTES` | максимальный размер JSON-ответа TMDB | `5242880` |
| `POSTER_ALLOWED_HOSTS` | HTTPS-хосты, с которых Telegram может получать постеры | `image.tmdb.org` |
| `MEDIA_ROOT` | каталог чтения старых локальных постеров | `media` |
| `SQLITE_BUSY_TIMEOUT_MS` | ожидание занятого SQLite writer-lock | `15000` |
| `REDIS_URL` | адрес Redis; пустое значение включает FSM в памяти | пусто |
| `MEDIA_WORKER_TIMEZONE` | зона вычисления расписания worker | `Europe/Moscow` |
| `MEDIA_REFRESH_BATCH_SIZE` | размер порции записей одного прохода | `50` |
| `MEDIA_REFRESH_CONCURRENCY` | одновременно обновляемые тайтлы | `3` |
| `MEDIA_REFRESH_LOCK_TTL_SECONDS` | TTL обновляемого Redis-lock | `21600` |
| `MEDIA_REFRESH_RETRIES` | попытки при timeout, 429 и 5xx | `3` |
| `FSM_TTL_SECONDS` | срок жизни незавершённого FSM-диалога | `86400` |
| `UPDATE_TASKS_CONCURRENCY_LIMIT` | максимум одновременно обрабатываемых Telegram updates | `32` |
| `USER_THROTTLE_MAX_UPDATES` | допустимое число updates одного пользователя за окно | `5` |
| `USER_THROTTLE_PERIOD_SECONDS` | размер окна per-user throttling в секундах | `1` |
| `USER_THROTTLE_MAX_USERS` | максимум пользователей в памяти throttling | `10000` |

Для совместимого proxy необходимо одновременно изменить `TMDB_URL` и явно
добавить его hostname в `TMDB_ALLOWED_HOSTS`. Разрешён только HTTPS. Не
добавляйте в allowlist чужие или недоверенные серверы: они получат Bearer-токен.
HTTP-редиректы TMDB-клиент не выполняет, чтобы токен нельзя было перенаправить
на другой адрес.

Полные URL постеров также проходят отдельный allowlist
`POSTER_ALLOWED_HOSTS`; HTTP, URL с credentials и неизвестные хосты
отклоняются. При добавлении собственного доверенного CDN его hostname нужно
указать явно.

В Compose значения хранилища задаются специально для контейнеров:
`DATABASE_URL=sqlite:////data/bot.db`, `MEDIA_ROOT=/data/media` и
`REDIS_URL=redis://redis:6379/0`. Redis не публикует порт на хост, хранит только
временные FSM-данные и ограничен 64 МБ памяти. Без `REDIS_URL` локальный запуск
использует память процесса, поэтому незавершённые диалоги пропадут после
перезапуска.

Новые постеры на диск не загружаются: бот передаёт Telegram уменьшенный TMDB
URL `w500`, после первой отправки сохраняет полученный Telegram `file_id` в
SQLite и использует его повторно. `MEDIA_ROOT` нужен только для чтения файлов,
которые могли остаться от предыдущих версий.

Compose также ограничивает bot-контейнер одним CPU, 512 МБ RAM и 128 PID, а
Redis — 0,5 CPU, 128 МБ RAM и 64 PID. Входящие updates обрабатываются не более
чем 32 одновременно; пользовательские bursts сверх заданного окна отбрасываются
до запуска handlers и обращений к SQLite, Redis или TMDB.

## Media worker

`media-worker` постоянно запущен, но между заданиями спит через `asyncio.sleep`
до ближайшего запуска. Он обновляет каталог в 02:00, рассылает новые серии в
12:00 и независимо запускает новостные слоты по `Europe/Moscow`. SQLite
`CURRENT_TIMESTAMP` остаётся в UTC; московская зона используется только при
выборе следующего момента запуска.

Новости по умолчанию включены после `/start`; пользователь может отключить или
снова включить их кнопкой в главном меню. Слоты идут каждые два часа с 10:00 до
22:00 со случайным смещением до пяти минут; первый слот не выходит за нижнюю
границу 10:00. Пропущенные после перезапуска слоты не догоняются.

Каждый запуск делает один логический запрос `/v1/news/all`, ограниченный русским языком,
категорией entertainment и доменами из `NEWS_ALLOWED_DOMAINS`. Результаты
сортируются по `published_at`, а не выбираются случайно. Допускаются только
статьи не старше `NEWS_MAX_AGE_HOURS` с полным описанием и рабочим JPEG, PNG или
WebP. Favicon и оборванное поставщиком описание отклоняются. Изображение
загружается и проверяется до
рассылки, а после первой отправки переиспользуется через Telegram `file_id`.
Если API оборвал описание, бот читает только полный `meta description` исходной
страницы, но не копирует тело статьи. Если готовый caption длиннее лимита
Telegram в 1024 символа, бот сохраняет заголовок и источник, а описание обрезает
только у самой границы лимита и добавляет `…`. Подходящие
кандидаты и их состояния `candidate/selected/sent/rejected` хранятся в SQLite:
успешная доставка фиксируется отдельно для каждого пользователя, поэтому после
перезапуска рассылка продолжается с недоставленных чатов. Завершённые записи
удаляются через `NEWS_RETENTION_DAYS`. При временной ошибке TheNewsAPI воркер
может использовать уже сохранённую свежую статью, а суточный бюджет учитывает
каждую физическую попытку HTTP-запроса, включая retry.

- Во вторник–воскресенье daily-проход выбирает активные `series`
  со статусом `Returning Series`, `Planned`, `In Production` либо
  `tmdb_in_production=1`, если release-проверка старше 23 часов.
- Тот же daily-проход проверяет будущие фильмы и сериалы, пока хотя бы у одного
  пользователя они находятся в «Хочу посмотреть». После выхода тайтл получает
  `is_released=1`, а пользователям создаётся устойчивое уведомление.
- В понедельник weekly-проход выбирает все series независимо от статуса, если
  metadata-проверка старше 6 дней 23 часов. Он одновременно обновляет daily
  timestamp, поэтому второй запрос активных тайтлов в понедельник не нужен.
- Вышедшие `full_length` не обновляются автоматически; будущие фильмы выходят
  из daily-выборки сразу после подтверждения релиза.
- При старте worker сначала проверяет просроченные timestamps: после простоя он
  догоняет weekly, а если weekly не нужен — daily, и лишь затем засыпает.

Пользователь может включить отслеживание не более чем для 50 активных сериалов.
Подписка хранится в `user_media` и не создаёт дополнительных TMDB-запросов:
один общий `media` обновляется один раз независимо от числа подписчиков. Если
число доступных эпизодов выросло, worker одним SQL-запросом сохраняет локальные
уведомления для всех подписчиков. Изменения описания, рейтинга и постера в
рассылку не попадают. Когда TMDB больше не считает сериал активным, подписки
автоматически выключаются; уведомление о последней серии при этом сохраняется.

В 12:00 по `Europe/Moscow` тот же worker отправляет каждому пользователю одно
сообщение со списком новых серий. В сообщении показывается до 10 сериалов, а
остальные доступны через inline-пагинацию. Неотправленные события остаются в
SQLite и повторяются при следующем запуске рассылки.

Будущий тайтл можно добавить только в «Хочу посмотреть»: действия просмотра,
оценки и прогресса скрыты и дополнительно запрещены на уровне обработчиков.
После подтверждения релиза worker отправляет уведомление «Можно смотреть», и
обычные действия библиотеки становятся доступны. Для сериала релиз считается
доступным после появления первой вышедшей серии, для фильма — по статусу и дате
релиза TMDB.

Один тайтл обрабатывается так: worker читает `media_id/tmdb_id`, без SQLite
transaction получает `/tv/{tmdb_id}` и нужные сезоны, сравнивает снимок с
каталогом, затем открывает короткую transaction. Изменения названий обновляют
нормализованный поисковый индекс; изменение `poster_path` сбрасывает
`telegram_poster_file_id`; `media_seasons` и общие числа эпизодов обновляются без
уменьшения уже доступного пользователям количества. Таблицы `user_media` и
`user_season_progress` worker не изменяет. Если данных не изменилось,
записываются только timestamps проверки и сбрасывается прошлая ошибка.

Проход читает записи порциями по 50 и одновременно обрабатывает максимум три.
Lua-ограничитель в Redis делит бюджет 9 запросов/с между bot и worker. Redis-lock
с уникальным token обновляет TTL во время работы и снимается compare-and-delete,
поэтому автоматические и ручные задания не пересекаются.

Ошибки одного тайтла не прерывают остальные: timeout/5xx/429 повторяются с
паузой, причём `Retry-After` создаёт общий Redis cooldown; 404 записывается как
`not_found`; последняя ошибка видна в `media.tmdb_refresh_error`. Ответ 401/403
немедленно прекращает job как ошибка TMDB credentials. Уже закоммиченные записи
сохраняются, а после аварии stale timestamps позволяют продолжить обход.

Ручное управление использует тот же контейнер, код, lock и лимитер:

```bash
make media-refresh-daily
make media-refresh-weekly
make media-refresh id=42
make media-refresh-tmdb id=1399
make media-refresh-dry id=42
make series-notify
make news-broadcast
make media-worker-logs
```

`media-refresh-dry` делает реальные TMDB-запросы и печатает изменения
`before -> after`, но не изменяет SQLite и timestamps. Daily/weekly-команды
обрабатывают только записи, которые просрочены по соответствующему timestamp.
`series-notify` вручную запускает тот же этап рассылки, который выполняется в
12:00, и не обращается к TMDB. `news-broadcast` вручную выбирает самую свежую
подходящую новость из доверенного источника, проверяет изображение и рассылает
её подписанным пользователям.

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
- не монтирует `bot_data`, поэтому не видит и не изменяет рабочую SQLite-базу
  и legacy-файлы постеров;
- завершается вместе с pytest, после чего `--rm` удаляет контейнер;
- оставляет собранный test-образ и BuildKit-кэш для ускорения следующего запуска.

На слабом сервере запускайте ровно один pytest-worker:

```bash
make test TEST_PROCESSES=1
```

Makefile сначала выполняет `docker compose --profile test build test`, затем
создаёт одноразовый контейнер командой
`docker compose --profile test run --rm test pytest -q -n 2`. По умолчанию
pytest использует два параллельных worker-процесса; дополнительные фоновые
сервисы при этом не запускаются. Значение можно переопределить через
`TEST_PROCESSES` с учётом доступных CPU и памяти.

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
Перед локальным production-запуском команда `make secure-files` выставляет
`0600` для `config/.env` и существующего `bot.db`. `make start-local` вызывает
её автоматически. При старте бот откажется работать, если `.env` или файл базы
доступен группе либо остальным пользователям, и подскажет команду `chmod 600`.
Новые файлы базы, WAL и SHM создаются с `umask 077` как локально, так и в
контейнере.

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
├── jobs/               # media-worker, расписание и refresh orchestration
├── lang/ru/            # пользовательские тексты
├── keyboards/          # inline/reply-клавиатуры
├── tmdb*.py            # API-клиент, модели, matching и совместимый фасад
└── posters.py          # TMDB URL, Telegram file_id и legacy local fallback
```

Обработчики отвечают за Telegram-взаимодействие, сервисы — за правила предметной
области, а слой `database` — за хранение. FSM сохраняет незавершённый контекст
диалога: в Redis на сервере и в памяти при локальном запуске без `REDIS_URL`.
Постоянные пользовательские данные всегда находятся в SQLite.

## Полезные команды

```bash
make help       # список основных целей
make build      # пересобрать production-образ
make deploy     # пересобрать и пересоздать bot и media-worker
make lint       # проверить Ruff без изменения файлов
make format     # исправить и отформатировать Python-код
make restart    # алиас для make deploy
make logs       # следить за логами bot, media-worker и redis
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
