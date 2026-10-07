# RuTracker Public: один search-плагин qBittorrent

`rutracker_public.py` — один устанавливаемый файл для qBittorrent. Он переносит
публичную схему JacRed: `viewforum.php` → локальный индекс → `viewtopic.php` → magnet.
Логин RuTracker не нужен.

## Установка

В qBittorrent: Поиск → Поисковые плагины → Установить новый → выбрать
`rutracker_public.py`.

При первом заблокированном HTTP-запросе плагин сам скачивает в собственный каталог
данных:

- portable `uv` с проверкой SHA-256;
- Python-пакеты Camoufox и Playwright;
- native Camoufox Firefox с fingerprint-патчами;
- модель fingerprint и addon, которые нужны Camoufox.

Docker, системный Python `pip`, Selenium, Firefox, Playwright и FlareSolverr
пользователю устанавливать не нужно. Runtime запускается отдельным приватным
worker-процессом плагина, обменивается с ним HTML через JSON-lines и закрывается
после поиска. Cookie и HTML worker не печатает в stdout qBittorrent.

Первое скачивание большое: native Camoufox занимает примерно 1.3 ГБ, затем
runtime переиспользуется из `rutracker_public.data`. Для скачивания и запуска
есть отдельные лимиты `download_seconds` (900) и `startup_seconds` (60).
Поддержаны Linux/macOS x86_64 и ARM64; Windows native-сборка Camoufox этим
плагином пока не заявляется.

Camoufox запускается headless с native fingerprint, а не с JS-подменой:
OS/platform, navigator, WebGL, canvas, fonts, audio, WebRTC, timezone/locale,
screen/window и automation-поведение задаются самим браузером. После загрузки
страницы плагин ждёт challenge, проверяет clearance и использует TRAWL-подход:
Turnstile iframe/checkbox, затем клавиатурный fallback. Токены не подделываются.

## Подтверждённая живая проверка

На Linux x86_64 цепочка прошла целиком через штатный `nova2.py` qBittorrent:

```text
один rutracker_public.py
→ автоматический Camoufox bootstrap
→ Cloudflare challenge
→ native fingerprint Camoufox
→ 50 тем RuTracker
→ поиск Dream Scenario
→ magnet в формате qBittorrent
→ закрытие worker
```

Индекс SQLite сохраняется рядом с `.py`. Первый запрос добавляет только
ограниченный объём; следующие запросы двигают курсор и расширяют индекс.

## Ограничения

- Это частичный индекс публичных форумов, не `tracker.php`-поиск по всему сайту.
- По умолчанию включены фильмы, сериалы/мультсериалы и аниме из карты QuickParse JacRed.
- За поиск обходится максимум четыре страницы разделов и выдаётся до 25 совпадений.
- На один запрос используется один native Camoufox worker.
- Одновременные поиски могут одновременно потребовать много RAM/CPU.
- При принудительном убийстве qBittorrent worker может остаться; штатный `finally`
  закрывает его при обычной ошибке и завершении поиска.
- Старый `solver_url` остаётся необязательным fallback для уже работающего
  FlareSolverr `/v1`; плагин его не запускает и не останавливает.

## Настройки

Рядом с плагином можно положить `rutracker_public.json`. Основные параметры:

- `download_seconds` — лимит bootstrap, по умолчанию 900;
- `startup_seconds` — лимит запуска Camoufox, по умолчанию 60;
- `search_seconds`, `timeout_seconds`, `request_delay`, `result_limit`;
- `pages_per_search`, `pages_per_forum`, `forums`;
- `solver_url` — внешний FlareSolverr `/v1`, пусто по умолчанию.

`compose.trawl.yml` больше не используется. `rutracker_public.example.json`
оставлен для ограниченного теста одного раздела.

## Проверка разработчиком

Офлайн-тесты не скачивают 1.3 ГБ:

```sh
python3 -m unittest discover -s . -p 'test_*.py' -v
```

Для живой проверки используется штатный qBittorrent `nova2.py`; она должна
запускать плагин из отдельной копии и подтверждать результат `Dream Scenario`,
8 полей строки qBittorrent и отсутствие worker-процесса после завершения.

## Источники

- Формат плагина: `qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin.md`.
- Парсер и карта публичных RuTracker-разделов: `jacred-fdb/jacred`,
  `Infrastructure/Trackers/Rutracker/RutrackerParser.cs`.
- Native browser/fingerprint: `daijro/camoufox`.
- Challenge wait/click strategy: `germondai/trawl`,
  `packages/tiers/src/utils/challengeWait.ts`.

Лицензия проекта: AGPL-3.0-or-later. Плагин пока не установлен в рабочий
qBittorrent владельца и не опубликован в каталоге.
