# media

Общий media-сервис: бинари (картинки/аудио/файлы) для всех клиентов с
sha256-дедупликацией, on-disk шардингом, thumbnails и pull-модель orphan GC.

Карта: `~/claude-workspace/history/2026-05-26-media-service-spec.md`.

## Стек

FastAPI + SQLAlchemy 2.x async + asyncpg + Alembic + Pillow + libwebp + APScheduler.
БД `media_dev` в общем `db_shared`. Storage — bind-mount `/srv/storage` снаружи
контейнера.

## Endpoints

| Метод | Путь | Auth | Назначение |
|---|---|---|---|
| `POST` | `/api/v1/assets` | forward_auth (write) | Multipart upload. sha256-dedup; thumbnail генерится для image/* синхронно. |
| `GET` | `/api/v1/assets/{id}` | **public** | Stream blob с `Cache-Control: public, max-age=31536000, immutable` + ETag по sha256. |
| `GET` | `/api/v1/assets/{id}/thumb` | **public** | 256×256 WebP thumbnail. 404 если `has_thumb=false`. |
| `HEAD` | `/api/v1/assets/{id}` | public | Headers без body — exists-check. |
| `POST` | `/api/v1/gc/run` | curator | Ad-hoc GC. `?grace_seconds=N` переопределяет grace для smoke. |
| `GET` | `/api/v1/gc/last` | curator | Последний `gc_runs`. |
| `GET` | `/api/info` | (за forward_auth) | Service + version + db-health. |

POST response:
```json
{"id":"<uuid>","url":"/api/v1/assets/<uuid>","thumbUrl":"/api/v1/assets/<uuid>/thumb","mime":"image/jpeg","bytes":30716,"sha256":"...","deduplicated":false}
```

## Storage layout

```
/srv/storage/
├── <aa>/<bb>/<sha256>               # blob
├── thumbs/<aa>/<bb>/<sha256>.webp   # thumbnail (если image/*)
└── tmp/                             # upload-staging (на том же FS для atomic rename)
```

## Orphan GC

Pull-модель: APScheduler раз в сутки (03:00 UTC) опрашивает consumers
`MEDIA_CONSUMERS=board=http://board_dev_app:8000/api/v1/media-refs;...` за
shared secret `X-Media-GC-Token`. Union refs — это «referenced». Assets с
`deleted_at IS NULL` и `created_at < NOW - grace_days*86400_000` и `id ∉
referenced` помечаются `deleted_at=NOW`, blob + thumb удаляются с диска.

Если хоть один consumer не ответил → abort (без полной картины refs удалять
опасно). Залогируется в `gc_runs.error_text`, retry на следующем cron.

## Client contract: `attrs.asset_id`

Клиентские сервисы хранят в своих attrs **только `asset_id`** (UUID). URL
строится фронтом из `${VITE_MEDIA_BASE}/api/v1/assets/{asset_id}`.

Каждый consumer обязан реализовать `GET /api/v1/media-refs` (за
`X-Media-GC-Token`), возвращающий `{asset_ids: [...]}` — DISTINCT по всем
ссылкам на media из его БД.

## Запуск

В составе общего dev-стенда (docker compose, network `shared`):

```bash
cp .env.example .env
# Подставить пароли БД и MEDIA_GC_TOKEN
docker compose up -d --build
docker exec media_dev_app alembic upgrade head
curl http://127.0.0.1:8028/api/info
```
