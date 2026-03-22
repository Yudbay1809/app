import os
import hashlib
import time
import shutil
import subprocess
from fastapi import UploadFile
from PIL import Image, ImageOps

MEDIA_DIR = "storage/media"
MAX_IMAGE_BYTES = int(os.getenv("SIGNAGE_MAX_IMAGE_BYTES", str(15 * 1024 * 1024)))
MAX_VIDEO_BYTES = int(os.getenv("SIGNAGE_MAX_VIDEO_BYTES", str(250 * 1024 * 1024)))
RECOMMENDED_IMAGE_BYTES = int(os.getenv("SIGNAGE_RECOMMENDED_IMAGE_BYTES", str(2 * 1024 * 1024)))
RECOMMENDED_VIDEO_BYTES = int(os.getenv("SIGNAGE_RECOMMENDED_VIDEO_BYTES", str(50 * 1024 * 1024)))
IMAGE_MAX_WIDTH = int(os.getenv("SIGNAGE_IMAGE_MAX_WIDTH", "1920"))
IMAGE_MAX_HEIGHT = int(os.getenv("SIGNAGE_IMAGE_MAX_HEIGHT", "1080"))
IMAGE_JPEG_QUALITY = int(os.getenv("SIGNAGE_IMAGE_JPEG_QUALITY", "82"))
VIDEO_MAX_WIDTH = int(os.getenv("SIGNAGE_VIDEO_MAX_WIDTH", "1920"))
VIDEO_TARGET_BITRATE = os.getenv("SIGNAGE_VIDEO_TARGET_BITRATE", "4M")
VIDEO_AUDIO_BITRATE = os.getenv("SIGNAGE_VIDEO_AUDIO_BITRATE", "128k")
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


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _optimize_image_file(path: str, filename: str, size: int) -> tuple[str, int, str]:
    _, ext = os.path.splitext(filename.lower())
    try:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)
        width, height = img.size
        needs_resize = width > IMAGE_MAX_WIDTH or height > IMAGE_MAX_HEIGHT
        needs_reencode = ext not in {".jpg", ".jpeg"} or size > RECOMMENDED_IMAGE_BYTES
        if not needs_resize and not needs_reencode:
            return path, size, _sha256_file(path)

        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        elif img.mode == "L":
            img = img.convert("RGB")
        if needs_resize:
            img.thumbnail((IMAGE_MAX_WIDTH, IMAGE_MAX_HEIGHT))

        safe_base, _ = os.path.splitext(os.path.basename(filename))
        safe_base = safe_base.replace(" ", "-").strip("-") or "media"
        new_filename = f"{safe_base}-opt.jpg"
        new_path = os.path.join(MEDIA_DIR, new_filename)
        img.save(
            new_path,
            format="JPEG",
            quality=IMAGE_JPEG_QUALITY,
            optimize=True,
            progressive=True,
        )

        try:
            if os.path.abspath(new_path) != os.path.abspath(path):
                os.remove(path)
        except OSError:
            pass

        new_size = os.path.getsize(new_path)
        return new_path, new_size, _sha256_file(new_path)
    except Exception:
        return path, size, _sha256_file(path)


def _optimize_video_file(path: str, filename: str, size: int) -> tuple[str, int, str]:
    if size <= RECOMMENDED_VIDEO_BYTES:
        return path, size, _sha256_file(path)

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return path, size, _sha256_file(path)

    safe_base, _ = os.path.splitext(os.path.basename(filename))
    safe_base = safe_base.replace(" ", "-").strip("-") or "media"
    new_filename = f"{safe_base}-opt.mp4"
    new_path = os.path.join(MEDIA_DIR, new_filename)
    scale_filter = f"scale='min({VIDEO_MAX_WIDTH},iw)':-2"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        path,
        "-vf",
        scale_filter,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        VIDEO_TARGET_BITRATE,
        "-maxrate",
        VIDEO_TARGET_BITRATE,
        "-bufsize",
        "8M",
        "-c:a",
        "aac",
        "-b:a",
        VIDEO_AUDIO_BITRATE,
        new_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        new_size = os.path.getsize(new_path)
        if new_size > 0:
            try:
                if os.path.abspath(new_path) != os.path.abspath(path):
                    os.remove(path)
            except OSError:
                pass
            return new_path, new_size, _sha256_file(new_path)
    except Exception:
        pass
    return path, size, _sha256_file(path)


def _maybe_optimize_media(
    path: str, media_type: str, filename: str, size: int
) -> tuple[str, int, str]:
    if media_type == "image":
        return _optimize_image_file(path, filename, size)
    if media_type == "video":
        return _optimize_video_file(path, filename, size)
    return path, size, _sha256_file(path)


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
    final_path, final_size, final_checksum = _maybe_optimize_media(
        path, media_type, filename, size
    )
    return final_path.replace("\\", "/"), final_size, final_checksum
