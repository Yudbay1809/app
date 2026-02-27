from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text
import os
import re

DATABASE_URL = "sqlite:///./signage.db"  # ganti ke postgres nanti

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


def ensure_sqlite_schema():
    """
    Lightweight runtime schema patching for SQLite.

    `Base.metadata.create_all()` won't add new columns to existing tables.
    This keeps local/dev installs working without requiring Alembic.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        cols = conn.execute(text("PRAGMA table_info(device)")).fetchall()
        col_names = {row[1] for row in cols}  # (cid, name, type, notnull, dflt_value, pk)
        if "orientation" not in col_names:
            conn.execute(text("ALTER TABLE device ADD COLUMN orientation VARCHAR DEFAULT 'portrait'"))
        if "owner_account" not in col_names:
            conn.execute(text("ALTER TABLE device ADD COLUMN owner_account VARCHAR"))
        if "legacy_id" not in col_names:
            conn.execute(text("ALTER TABLE device ADD COLUMN legacy_id VARCHAR"))
        if "client_ip" not in col_names:
            conn.execute(text("ALTER TABLE device ADD COLUMN client_ip VARCHAR"))
        if "cached_media_ids" not in col_names:
            conn.execute(text("ALTER TABLE device ADD COLUMN cached_media_ids TEXT"))
        if "media_cache_updated_at" not in col_names:
            conn.execute(text("ALTER TABLE device ADD COLUMN media_cache_updated_at DATETIME"))
        duplicate_ip_rows = conn.execute(
            text(
                "SELECT id, client_ip FROM device "
                "WHERE client_ip IS NOT NULL AND trim(client_ip) <> '' "
                "ORDER BY rowid ASC"
            )
        ).fetchall()
        seen_ips: set[str] = set()
        for device_id, client_ip in duplicate_ip_rows:
            normalized_ip = (client_ip or "").strip()
            if not normalized_ip:
                continue
            if normalized_ip in seen_ips:
                conn.execute(
                    text("UPDATE device SET client_ip=NULL WHERE id=:id"),
                    {"id": device_id},
                )
            else:
                seen_ips.add(normalized_ip)
        try:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_device_client_ip "
                    "ON device(client_ip) "
                    "WHERE client_ip IS NOT NULL AND trim(client_ip) <> ''"
                )
            )
        except Exception:
            pass

        if "orientation" in col_names or cols:
            conn.execute(text("UPDATE device SET orientation='portrait' WHERE orientation IS NULL OR orientation=''"))

        device_rows = conn.execute(text("SELECT id FROM device ORDER BY rowid ASC")).fetchall()
        id_values = [row[0] for row in device_rows if row and row[0]]
        existing_simple = {
            int(match.group(1))
            for value in id_values
            for match in [re.fullmatch(r"Device-(\d{4,})", str(value))]
            if match is not None
        }
        next_seq = (max(existing_simple) + 1) if existing_simple else 1
        used_ids = set(str(value) for value in id_values)

        for old_id in id_values:
            old = str(old_id)
            if re.fullmatch(r"Device-(\d{4,})", old):
                continue
            candidate = f"Device-{next_seq:04d}"
            while candidate in used_ids:
                next_seq += 1
                candidate = f"Device-{next_seq:04d}"
            next_seq += 1

            conn.execute(
                text("UPDATE device SET id=:new_id, legacy_id=:legacy WHERE id=:old_id"),
                {"new_id": candidate, "legacy": old, "old_id": old},
            )
            conn.execute(
                text("UPDATE screen SET device_id=:new_id WHERE device_id=:old_id"),
                {"new_id": candidate, "old_id": old},
            )
            used_ids.add(candidate)
            used_ids.discard(old)

        media_cols = conn.execute(text("PRAGMA table_info(media)")).fetchall()
        media_col_names = {row[1] for row in media_cols}
        if {"id", "name", "path"}.issubset(media_col_names):
            rows = conn.execute(
                text(
                    "SELECT id, name, path FROM media "
                    "WHERE name IS NULL OR trim(name)='' OR lower(trim(name))='unnamed'"
                )
            ).fetchall()
            for media_id, _name, media_path in rows:
                normalized = os.path.basename((media_path or "").replace("\\", "/")).strip()
                if not normalized:
                    normalized = f"media-{media_id}"
                conn.execute(
                    text("UPDATE media SET name=:name WHERE id=:id"),
                    {"name": normalized, "id": media_id},
                )

        screen_cols = conn.execute(text("PRAGMA table_info(screen)")).fetchall()
        screen_col_names = {row[1] for row in screen_cols}
        if "active_playlist_id" not in screen_col_names:
            conn.execute(text("ALTER TABLE screen ADD COLUMN active_playlist_id VARCHAR"))
        if "grid_preset" not in screen_col_names:
            conn.execute(text("ALTER TABLE screen ADD COLUMN grid_preset VARCHAR DEFAULT '1x1'"))
        if "transition_duration_sec" not in screen_col_names:
            conn.execute(text("ALTER TABLE screen ADD COLUMN transition_duration_sec INTEGER DEFAULT 1"))
        conn.execute(
            text(
                "UPDATE screen SET grid_preset='1x1' "
                "WHERE grid_preset IS NULL OR trim(grid_preset)=''"
            )
        )
        conn.execute(
            text(
                "UPDATE screen SET transition_duration_sec=1 "
                "WHERE transition_duration_sec IS NULL"
            )
        )
        conn.execute(
            text(
                "UPDATE screen SET transition_duration_sec=0 "
                "WHERE transition_duration_sec < 0"
            )
        )
        conn.execute(
            text(
                "UPDATE screen SET transition_duration_sec=30 "
                "WHERE transition_duration_sec > 30"
            )
        )

        schedule_cols = conn.execute(text("PRAGMA table_info(schedule)")).fetchall()
        schedule_col_names = {row[1] for row in schedule_cols}
        if "note" not in schedule_col_names:
            conn.execute(text("ALTER TABLE schedule ADD COLUMN note VARCHAR"))
        if "countdown_sec" not in schedule_col_names:
            conn.execute(text("ALTER TABLE schedule ADD COLUMN countdown_sec INTEGER"))
        conn.execute(
            text(
                "UPDATE schedule SET countdown_sec=NULL "
                "WHERE countdown_sec IS NOT NULL AND countdown_sec <= 0"
            )
        )

        playlist_cols = conn.execute(text("PRAGMA table_info(playlist)")).fetchall()
        playlist_col_names = {row[1] for row in playlist_cols}
        if "is_flash_sale" not in playlist_col_names:
            conn.execute(
                text("ALTER TABLE playlist ADD COLUMN is_flash_sale INTEGER DEFAULT 0")
            )
        if "flash_note" not in playlist_col_names:
            conn.execute(text("ALTER TABLE playlist ADD COLUMN flash_note VARCHAR"))
        if "flash_countdown_sec" not in playlist_col_names:
            conn.execute(
                text("ALTER TABLE playlist ADD COLUMN flash_countdown_sec INTEGER")
            )
        if "flash_items_json" not in playlist_col_names:
            conn.execute(text("ALTER TABLE playlist ADD COLUMN flash_items_json VARCHAR"))
        conn.execute(
            text(
                "UPDATE playlist SET is_flash_sale=0 "
                "WHERE is_flash_sale IS NULL"
            )
        )
        conn.execute(
            text(
                "UPDATE playlist SET flash_countdown_sec=NULL "
                "WHERE flash_countdown_sec IS NOT NULL AND flash_countdown_sec <= 0"
            )
        )

        flash_sale_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='flash_sale_config'")
        ).fetchone()
        if flash_sale_exists:
            flash_sale_cols = conn.execute(text("PRAGMA table_info(flash_sale_config)")).fetchall()
            flash_sale_col_names = {row[1] for row in flash_sale_cols}
            if "is_draft" not in flash_sale_col_names:
                conn.execute(text("ALTER TABLE flash_sale_config ADD COLUMN is_draft INTEGER DEFAULT 0"))
            if "warmup_minutes" not in flash_sale_col_names:
                conn.execute(text("ALTER TABLE flash_sale_config ADD COLUMN warmup_minutes INTEGER"))
            conn.execute(
                text(
                    "UPDATE flash_sale_config SET is_draft=0 "
                    "WHERE is_draft IS NULL"
                )
            )
            conn.execute(
                text(
                    "UPDATE flash_sale_config SET warmup_minutes=NULL "
                    "WHERE warmup_minutes IS NOT NULL AND warmup_minutes <= 0"
                )
            )

        sync_state_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='device_sync_state'")
        ).fetchone()
        if sync_state_exists:
            sync_state_cols = conn.execute(text("PRAGMA table_info(device_sync_state)")).fetchall()
            sync_state_col_names = {row[1] for row in sync_state_cols}
            if "ack_source" not in sync_state_col_names:
                conn.execute(text("ALTER TABLE device_sync_state ADD COLUMN ack_source VARCHAR"))
            if "ack_reason" not in sync_state_col_names:
                conn.execute(text("ALTER TABLE device_sync_state ADD COLUMN ack_reason TEXT"))
            if "ack_at" not in sync_state_col_names:
                conn.execute(text("ALTER TABLE device_sync_state ADD COLUMN ack_at DATETIME"))
