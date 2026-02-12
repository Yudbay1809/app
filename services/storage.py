import os
import hashlib
from fastapi import UploadFile

MEDIA_DIR = "storage/media"

def ensure_storage() -> None:
    os.makedirs(MEDIA_DIR, exist_ok=True)

def save_file(file: UploadFile) -> tuple[str, int, str]:
    ensure_storage()
    content = file.file.read()
    checksum = hashlib.sha256(content).hexdigest()
    filename = os.path.basename((file.filename or "upload.bin").strip()) or "upload.bin"
    path = os.path.join(MEDIA_DIR, filename)
    with open(path, "wb") as f:
        f.write(content)
    return path.replace("\\", "/"), len(content), checksum
