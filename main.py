from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.db import Base, engine
from app.api import media, device, playlist, schedule, screen
from app.services.storage import ensure_storage

Base.metadata.create_all(bind=engine)
ensure_storage()

app = FastAPI()
app.include_router(media.router)
app.include_router(device.router)
app.include_router(playlist.router)
app.include_router(schedule.router)
app.include_router(screen.router)

app.mount("/storage", StaticFiles(directory="storage"), name="storage")
