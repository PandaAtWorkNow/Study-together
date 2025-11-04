# README — как отдавать данные MiniApp’у и получать запись

Этот документ — пошаговая инструкция, как ваш backend (на aiogram + HTTP-микро-API) отдает MiniApp’у данные (услуги, мастера, свободные слоты) и как MiniApp/бот создают запись.

## 0) Коротко про архитектуру

**Компоненты:**

* **Frontend (MiniApp)** — HTML+JS, работает внутри Telegram.
* **Bot (aiogram 3.x)** — принимает апдейты (в т.ч. `web_app_data`).
* **HTTP-API** — тонкий REST-слой над вашей CRM/БД (может быть на FastAPI/Aiohttp).
  MiniApp ходит к нему за справочниками и слотами, а также (вариант А) создаёт запись.

> Рекомендация Telegram: при запросах из MiniApp на ваш сервер **проверять подпись `initData`** (seamless auth), а финальные действия подтверждать **MainButton** и/или `sendData`. Для проверки подписи используйте готовую функцию `aiogram.utils.web_app.check_webapp_signature`. ([docs.aiogram.dev][1])

---

## 1) Контракты API (что MiniApp ожидает от бэкенда)

Все ответы — `application/json`. Все время — **локальной таймзоны салона**. Даты — `YYYY-MM-DD`, время — `HH:mm`.

### 1.1 GET `/api/services`

**Назначение:** список услуг.

**Параметры:** нет.

**Ответ:**

```json
[
  { "id": 101, "name": "Стрижка", "duration_minutes": 60, "price": 1500 },
  { "id": 102, "name": "Маникюр", "duration_minutes": 90, "price": 2200 }
]
```

### 1.2 GET `/api/masters`

**Назначение:** список мастеров. Опционально фильтровать по услуге.

**Параметры (query):**

* `service_id` — *опционально* (число)

**Ответ:**

```json
[
  { "id": 201, "name": "Анна" },
  { "id": 202, "name": "Мария" }
]
```

### 1.3 GET `/api/slots`

**Назначение:** свободные слоты конкретного мастера под конкретную услугу на выбранную дату.

**Параметры (query):**

* `service_id` (обязательно)
* `master_id` (обязательно)
* `date` (обязательно, `YYYY-MM-DD`)

**Ответ:**

```json
{ "slots": ["10:00", "10:30", "11:30", "13:00"] }
```

или короче:

```json
["10:00", "10:30", "11:30", "13:00"]
```

### 1.4 POST `/api/bookings` (вариант А — создавать запись через HTTP)

**Назначение:** создать запись в CRM/БД с привязкой к Telegram-пользователю (по `initData`).

**Заголовки:**

* `X-Telegram-Init-Data: <initData>` — строка из `tg.initData` с фронта (для проверки подписи).

**Тело (JSON):**

```json
{
  "service_id": 101,
  "master_id": 201,
  "date": "2025-11-06",
  "time": "10:30",
  "note": "Без лака"
}
```

**Ответ 201:**

```json
{
  "id": 3456,
  "status": "confirmed",
  "service_id": 101,
  "master_id": 201,
  "date": "2025-11-06",
  "time": "10:30",
  "client": { "tg_user_id": 123456789, "first_name": "Ivan" }
}
```

---

## 2) Безопасность: проверка `initData` (seamless auth)

На фронте Telegram отдаёт в JS объект `Telegram.WebApp`, где:

* `tg.initData` — строка query-парам с подписью от Telegram.
* `tg.initDataUnsafe` — разобранная структура (нельзя доверять **без проверки** на сервере).

На сервере **обязательно** валидируйте подпись `initData`, чтобы убедиться, что запрос сделан реальным пользователем в реальном MiniApp. В aiogram 3 есть готовая функция:

```python
from aiogram.utils.web_app import check_webapp_signature

def is_valid_init_data(token: str, init_data: str) -> bool:
    return check_webapp_signature(token=token, init_data=init_data)
```

Алгоритм верификации следует требованиям Telegram (HMAC-SHA256 с ключом, производным от `WebAppData` и токена бота). Использование готовой функции избавляет от ошибок реализации. ([docs.aiogram.dev][1])

> Фронт при каждом запросе к `/api/*` шлёт заголовок `X-Telegram-Init-Data: tg.initData`. Сервер отклоняет запрос 401/403, если подпись невалидна/протухла.

---

## 3) Потоки данных (два рабочих варианта)

### Вариант А — «чистый HTTP»: запись создаётся сразу сервером

1. MiniApp:

   * Загружает `/api/services`, `/api/masters?service_id=…`, `/api/slots?...`.
   * Юзер выбирает услугу/мастера/дату/время.
   * Нажатие **MainButton** ⇒ `POST /api/bookings` с телом и заголовком `X-Telegram-Init-Data`.
2. Сервер:

   * Валидирует `initData`, извлекает `user.id`, создаёт запись в CRM/БД.
3. (Опционально) MiniApp вызывает `tg.sendData(JSON.stringify({type:"booking_created", booking_id}))`, чтобы бот показал подтверждение в чате.

### Вариант Б — «через sendData»: сервер создаёт запись в обработчике aiogram

1. MiniApp:

   * Загружает справочники и слоты через `/api/*`.
   * Нажатие **MainButton** ⇒ `tg.sendData(JSON.stringify({ type:"booking", service_id, master_id, date, time }))`.
2. Бот (aiogram):

   * Ловит `@router.message(F.web_app_data)`, парсит JSON, создаёт запись в CRM/БД и отвечает пользователю.

> В проде чаще берут **вариант А** (HTTP): вы сразу на сервере валидируете пользователя и можете делать любые действия; `sendData` при этом остаётся как опциональное уведомление в чат. ([core.telegram.org][2])

---

## 4) Пример реализации HTTP-API (FastAPI + проверка подписи)

Ниже — пример, как отдать контракты из п.1 и проверить `initData`. Внутри — заглушки доступа к БД (замените на вашу CRM-логику).

```python
# FILE: api.py
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from aiogram.utils.web_app import check_webapp_signature
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

app = FastAPI(title="Salon MiniApp API")

# --- Models ---
class Service(BaseModel):
    id: int
    name: str
    duration_minutes: int
    price: int

class Master(BaseModel):
    id: int
    name: str

class SlotsResponse(BaseModel):
    slots: List[str]

class BookingIn(BaseModel):
    service_id: int
    master_id: int
    date: str     # YYYY-MM-DD
    time: str     # HH:mm
    note: Optional[str] = None

class BookingOut(BaseModel):
    id: int
    status: str
    service_id: int
    master_id: int
    date: str
    time: str
    client: Dict[str, Any]

# --- Helpers ---
def ensure_auth(init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data")) -> Dict[str, Any]:
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-Init-Data")
    if not check_webapp_signature(token=BOT_TOKEN, init_data=init_data):
        raise HTTPException(status_code=403, detail="Invalid initData signature")
    # В этот момент init_data валидна. Можно распарсить querystring самому при необходимости.
    # Для простоты вернём "псевдо-профиль" (на практике распарсите user из init_data).
    return {"tg_user_id": "from_init_data"}  # TODO: извлечь user.id, username и т.д.

# --- Fake DB accessors (замените вашей CRM) ---
def db_list_services() -> List[Service]:
    return [
        Service(id=101, name="Стрижка", duration_minutes=60, price=1500),
        Service(id=102, name="Маникюр", duration_minutes=90, price=2200),
    ]

def db_list_masters(service_id: Optional[int]) -> List[Master]:
    # Пример фильтрации по услуге (если нужно)
    return [Master(id=201, name="Анна"), Master(id=202, name="Мария")]

def db_free_slots(service_id: int, master_id: int, date: str) -> List[str]:
    # Рассчёт: рабочие часы мастера - занятые брони - перерывы и т.д.
    return ["10:00", "10:30", "11:30", "13:00"]

def db_create_booking(user, data: BookingIn) -> BookingOut:
    # Сохраните запись в БД, учтите коллизии и транзакции
    return BookingOut(
        id=3456,
        status="confirmed",
        service_id=data.service_id,
        master_id=data.master_id,
        date=data.date,
        time=data.time,
        client={"tg_user_id": user["tg_user_id"]}
    )

# --- Endpoints ---
@app.get("/api/services", response_model=List[Service])
def services(_: Dict[str, Any] = Depends(ensure_auth)):
    return db_list_services()

@app.get("/api/masters", response_model=List[Master])
def masters(service_id: Optional[int] = None, _: Dict[str, Any] = Depends(ensure_auth)):
    return db_list_masters(service_id)

@app.get("/api/slots", response_model=SlotsResponse)
def slots(service_id: int, master_id: int, date: str, _: Dict[str, Any] = Depends(ensure_auth)):
    return SlotsResponse(slots=db_free_slots(service_id, master_id, date))

@app.post("/api/bookings", response_model=BookingOut, status_code=201)
def create_booking(payload: BookingIn, user=Depends(ensure_auth)):
    # Здесь важно повторно проверить доступность слота под конкретную услугу/мастера
    return db_create_booking(user, payload)
```

> Если не хотите поднимать FastAPI, аналогично можно сделать на `aiohttp.web` или встроить в существующий ASGI-стек. Главное — соблюдать контракты и проверять `initData`.

---

## 5) Обработчик в боте для варианта Б (через `sendData`)

Если MiniApp по нажатию MainButton делает `tg.sendData({...})`, бот получит сервис-сообщение `web_app_data`. Хендлер:

```python
# FILE: bot_handlers.py
import json
from aiogram import Router, F
from aiogram.types import Message

router = Router()

@router.message(F.web_app_data)
async def on_webapp_data(message: Message):
    raw = message.web_app_data.data
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        await message.answer("Не удалось прочитать данные из MiniApp.")
        return

    if payload.get("type") == "booking":
        # извлечь поля
        service_id = int(payload["service_id"])
        master_id  = int(payload["master_id"])
        date       = payload["date"]
        time       = payload["time"]

        # Здесь создайте запись в вашей CRM/БД (проверив, что слот ещё свободен)
        # booking_id = create_booking(...)

        await message.answer(f"✅ Запись создана: {date} {time}\nМастер #{master_id}, услуга #{service_id}")
    else:
        await message.answer("Получены данные MiniApp, тип не распознан.")
```

> В этом потоке вы не используете проверку `initData`, но Telegram всё равно отдает сообщение вашему боту от конкретного пользователя, что достаточно для большинства «несекретных» действий. Для строгой безопасности и интеграций с внешними API предпочтителен **вариант А**.

---

## 6) Как MiniApp «кормится» данными и отсылает подтверждение

1. При загрузке страницы MiniApp вызывает:

   * `GET /api/services` → заполняет `<select id="service">`.
   * При выборе услуги: `GET /api/masters?service_id=...` → `<select id="master">`.
   * При выборе мастера и даты: `GET /api/slots?service_id=...&master_id=...&date=...` → `<select id="time">`.
   * Все запросы сопровождаются заголовком `X-Telegram-Init-Data: tg.initData`.
2. Когда все поля заполнены, MiniApp показывает **MainButton**.
   Дальше два пути:

   * **HTTP-создание (вариант А):** MainButton ⇒ `POST /api/bookings` (c initData). Успех ⇒ `tg.sendData({type:"booking_created", ...})` (необязательно).
   * **Бот-создание (вариант Б):** MainButton ⇒ `tg.sendData({type:"booking", ...})`, обработка в aiogram-хендлере.

---

## 7) Пример запросов (для отладки)

> Подставьте реальный `initData` (его можно увидеть в консоли фронта), реальный токен и домен.

### 7.1 Получить услуги

```bash
curl -H "X-Telegram-Init-Data: <PASTE_INIT_DATA>" https://your.host/api/services
```

### 7.2 Получить мастеров под услугу 101

```bash
curl -H "X-Telegram-Init-Data: <PASTE_INIT_DATA>" "https://your.host/api/masters?service_id=101"
```

### 7.3 Получить слоты

```bash
curl -H "X-Telegram-Init-Data: <PASTE_INIT_DATA>" "https://your.host/api/slots?service_id=101&master_id=201&date=2025-11-06"
```

### 7.4 Создать запись (вариант А)

```bash
curl -X POST -H "Content-Type: application/json" \
     -H "X-Telegram-Init-Data: <PASTE_INIT_DATA>" \
     -d '{"service_id":101,"master_id":201,"date":"2025-11-06","time":"10:30"}' \
     https://your.host/api/bookings
```

---

## 8) Требования к фронту (что уже учтено в вашем HTML)

* Подключён `https://telegram.org/js/telegram-web-app.js`.
* На старте: `tg.ready()` и (при желании) `tg.expand()`.
* Для всех запросов к `/api/*` добавляем заголовок `X-Telegram-Init-Data: tg.initData`.
* Главное действие вешаем на `MainButton`:

  * Текст: «Подтвердить запись».
  * `mainButtonClicked` ⇒ либо `POST /api/bookings`, либо `tg.sendData(...)`.
* Для тестов в обычном браузере — фолбэк (alert/console), но без `initData` API вернёт 401.

Документация Telegram по `sendData`, MainButton и валидации `initData`: ([core.telegram.org][2])

---

## 9) Практические советы внедрения

* **Таймзона:** храните всё в UTC в БД, а MiniApp показывайте в локальной TZ салона. API может принимать локальные `date/time` и конвертировать в UTC при записи.
* **Слоты:** вычисляйте как `рабочие интервалы мастера` − `занятые брони` − `перерывы` − `буферы до/после`. Длительность услуги учитывайте при проверке коллизий.
* **Конкурентность:** создавая запись, используйте транзакцию/блокировку слота, чтобы два клиента не заняли один и тот же интервал.
* **CORS/HTTPS:** MiniApp требует HTTPS. Если фронт и API на одном домене — проще. Если разные домены — настройте CORS.
* **Ошибки:** возвращайте осмысленные коды (400 — валидация, 401/403 — auth, 409 — слот занят, 500 — внутренние).

---

## 10) Что именно вам нужно сделать сейчас

1. Поднять HTTP-API по контрактам из раздела 1 (лучше на FastAPI).
2. Внедрить проверку `initData` (`ensure_auth` из примера).
3. Подключить MiniApp к вашему домену API (в HTML заменить `API_BASE`).
4. Решить поток создания записи:

   * **А:** `POST /api/bookings` (рекомендуется), плюс при желании `tg.sendData` для «квитка» в чат.
   * **Б:** только `tg.sendData`, а запись создаёт хендлер aiogram.
5. Протестировать цепочку: услуга → мастер → дата → слоты → подтверждение → запись в БД → ответ пользователю.

[1]: https://docs.aiogram.dev/en/latest/utils/web_app.html?utm_source=chatgpt.com "WebApp - aiogram 3.22.0 documentation"
[2]: https://core.telegram.org/bots/webapps?utm_source=chatgpt.com "Telegram Mini Apps"