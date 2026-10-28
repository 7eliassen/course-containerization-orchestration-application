
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import os
import socket

from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx
import redis.asyncio as aioredis

from app.database import engine, get_db
from app.models import Base
from app import crud

logger = logging.getLogger("uvicorn.error")

OWNER = os.getenv("APP_OWNER", "anonymous")
SECRET_KEY = os.getenv("APP_SECRET", "default_secret")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
HOSTNAME = socket.gethostname()

GEOCODING_URL = "https://nominatim.openstreetmap.org/search"
WEATHER_URL = "https://weather.tk.gg/v1/forecast"

redis_client: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    Base.metadata.create_all(bind=engine)
    try:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connected: %s", REDIS_URL)
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — caching disabled", exc)
        redis_client = None
    yield
    if redis_client:
        await redis_client.aclose()


app = FastAPI(title="Personal Assist", lifespan=lifespan)


class NoteCreate(BaseModel):
    text: str


def _meta() -> dict:
    return {
        "hostname": HOSTNAME,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
async def root():
    return {
        "message": f"👋 Привет, {OWNER}!",
        "service": "personal-assistant",
        "version": "3.0",
        "endpoints": [
            "/me", "/notes", "/weather/{city}", "/secret/{key}",
            "/cache/stats",
        ],
        **_meta(),
    }


@app.get("/health")
async def health():
    redis_ok = False
    if redis_client:
        try:
            redis_ok = await redis_client.ping()
        except Exception:
            pass
    return {
        "status": "healthy",
        "owner": OWNER,
        "redis": redis_ok,
        **_meta(),
    }


@app.get("/me")
async def me():
    return {
        "owner": OWNER,
        "secret_prefix": SECRET_KEY[:6]
        if SECRET_KEY != "default_secret"
        else "NOT_SET",
    }


@app.get("/secret/{key}")
async def secret(key: str):
    if key == SECRET_KEY:
        return {
            "flag": f"LAB2_SUCCESS_{OWNER.upper()}",
            "message": "The secret key is correct!",
        }
    return {
        "error": "The secret key is incorrect",
        "hint": "Check the APP_SECRET environment variable",
    }


WEATHER_CODES: dict[int, str] = {
    0: "☀️ Ясно", 1: "🌤 Малооблачно", 2: "⛅ Переменная облачность",
    3: "☁️ Пасмурно", 45: "🌫 Туман", 48: "🌫 Изморозь",
    51: "🌦 Лёгкая морось", 53: "🌦 Морось", 55: "🌧 Сильная морось",
    61: "🌧 Небольшой дождь", 63: "🌧 Дождь", 65: "🌧 Сильный дождь",
    71: "🌨 Небольшой снег", 73: "🌨 Снег", 75: "❄️ Сильный снег",
    80: "🌦 Ливень", 81: "🌧 Сильный ливень", 82: "⛈ Штормовой ливень",
    95: "⛈ Гроза", 96: "⛈ Гроза с градом", 99: "⛈ Сильная гроза с градом",
}


def _cache_key(city: str) -> str:
    return f"weather:{OWNER}:{city.strip().lower()}"


async def _get_cached(city: str) -> dict | None:
    if not redis_client:
        return None
    try:
        raw = await redis_client.get(_cache_key(city))
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def _set_cached(city: str, data: dict) -> None:
    if not redis_client:
        return
    try:
        await redis_client.setex(
            _cache_key(city),
            CACHE_TTL,
            json.dumps(data, ensure_ascii=False),
        )
    except Exception:
        pass


@app.get("/weather/{city}")
async def weather(city: str):
    cached = await _get_cached(city)
    if cached:
        return {**cached, "source": "cache", **_meta()}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Геокодирование через Nominatim
            geo_resp = await client.get(
                GEOCODING_URL,
                params={
                    "city": city,
                    "format": "jsonv2",
                    "limit": 1,
                },
                headers={"User-Agent": "assist-py/1.0"},
            )
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()

            if not geo_data:
                return {
                    "error": f"City «{city}» not found",
                    **_meta(),
                }

            location = geo_data[0]
            lat = float(location["lat"])
            lon = float(location["lon"])
            city_name = location.get("name", city)
            country = location.get("display_name", "")

            # Получение погоды через зеркало Open-Meteo
            weather_resp = await client.get(
                WEATHER_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": (
                        "temperature_2m,relative_humidity_2m,"
                        "wind_speed_10m,weather_code"
                    ),
                },
            )
            weather_resp.raise_for_status()
            weather_data = weather_resp.json()["current"]

            code = weather_data.get("weather_code", -1)

            result = {
                "city": city_name,
                "country": country,
                "coordinates": {"lat": lat, "lon": lon},
                "temperature_c": weather_data["temperature_2m"],
                "humidity_pct": weather_data["relative_humidity_2m"],
                "wind_km_h": weather_data["wind_speed_10m"],
                "condition": WEATHER_CODES.get(code, f"Code {code}"),
                "owner": OWNER,
            }

            await _set_cached(city, result)
            return {**result, "source": "api", **_meta()}

    except Exception as e:
        logger.exception("Weather request failed for city %s", city)
        return {
            "error": f"Failed to get weather: {type(e).__name__}: {e}",
            **_meta(),
        }


@app.get("/cache/stats")
async def cache_stats():
    if not redis_client:
        return {"error": "Redis not available", **_meta()}
    try:
        pattern = f"weather:{OWNER}:*"
        keys = []
        async for key in redis_client.scan_iter(match=pattern):
            ttl = await redis_client.ttl(key)
            keys.append({"key": key, "ttl_seconds": ttl})
        return {
            "owner": OWNER,
            "cache_ttl_setting": CACHE_TTL,
            "cached_cities": len(keys),
            "keys": keys,
            **_meta(),
        }
    except Exception as e:
        return {"error": str(e), **_meta()}


@app.post("/notes")
async def create_note(note: NoteCreate, db: Session = Depends(get_db)):
    db_note = crud.create_note(db=db, text=note.text, owner=OWNER)
    return {
        "status": "saved",
        "note_id": db_note.id,
        "owner": db_note.owner,
        "text": db_note.text[:50],
    }


@app.get("/notes")
async def list_notes(db: Session = Depends(get_db)):
    db_notes = crud.get_notes(db=db, owner=OWNER)
    return {
        "owner": OWNER,
        "count": len(db_notes),
        "notes": [
            {
                "id": n.id,
                "text": n.text,
                "owner": n.owner,
                "created_at": n.created_at.isoformat(),
            }
            for n in db_notes
        ],
    }


@app.get("/notes/{note_id}")
async def get_note(note_id: int, db: Session = Depends(get_db)):
    note = crud.get_note_by_id(db=db, note_id=note_id)
    if not note:
        return {"error": f"Note {note_id} not found"}
    return {
        "id": note.id,
        "text": note.text,
        "owner": note.owner,
        "created_at": note.created_at.isoformat(),
    }


@app.delete("/notes/{note_id}")
async def delete_note(note_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_note(db=db, note_id=note_id)
    if not deleted:
        return {"error": f"Note {note_id} not found"}
    return {"status": "deleted", "note_id": note_id}
