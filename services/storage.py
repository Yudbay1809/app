import os
import hashlib
import time
from fastapi import UploadFile

MEDIA_DIR = "storage/media"
MAX_IMAGE_BYTES = int(os.getenv("SIGNAGE_MAX_IMAGE_BYTES", str(15 * 1024 * 1024)))
MAX_VIDEO_BYTES = int(os.getenv("SIGNAGE_MAX_VIDEO_BYTES", str(250 * 1024 * 1024)))
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov"}

def ensure_storage() -> None:
    os.makedirs(MEDIA_DIR, exist_ok=True)

def _normalized_media_type(raw: str | None) -> str:
    media_type = (raw or "").strip().lower()
    if media_type not in {"image", "video"}:
        raise ValueError("Tipe media tidak didukung. Gunakan image atau video.")
    return media_type


def _validate_extension(media_type: str, filename: str) -> str:
    _, ext = os.path.splitext(filename.lower())
    if media_type == "image" and ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Format gambar tidak didukung. Gunakan JPG/JPEG/PNG/WEBP.")
    if media_type == "video" and ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError("Format video tidak didukung. Gunakan MP4/WEBM/MKV/MOV.")
    return ext


def save_file(file: UploadFile, declared_type: str) -> tuple[str, int, str]:
    ensure_storage()
    media_type = _normalized_media_type(declared_type)
    content = file.file.read()
    if not content:
        raise ValueError("File kosong tidak bisa diupload.")
    checksum = hashlib.sha256(content).hexdigest()
    filename = os.path.basename((file.filename or "upload.bin").strip()) or "upload.bin"
    ext = _validate_extension(media_type, filename)
    size = len(content)
    if media_type == "image" and size > MAX_IMAGE_BYTES:
        raise ValueError(f"Ukuran gambar melebihi batas {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    if media_type == "video" and size > MAX_VIDEO_BYTES:
        raise ValueError(f"Ukuran video melebihi batas {MAX_VIDEO_BYTES // (1024 * 1024)} MB.")
    safe_name, _ = os.path.splitext(filename)
    safe_name = "".join(ch for ch in safe_name if ch.isalnum() or ch in {"-", "_", " "}).strip() or "media"
    stamped_filename = f"{safe_name}-{int(time.time() * 1000)}{ext}"
    path = os.path.join(MEDIA_DIR, stamped_filename)
    with open(path, "wb") as f:
        f.write(content)
    return path.replace("\\", "/"), size, checksum
