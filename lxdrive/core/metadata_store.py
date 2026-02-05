#!/usr/bin/env python3
"""
MetadataStore - SQLite-based file tracking for lX Drive

Provides persistent file_id tracking for accurate move/rename detection
without relying on heuristics or path comparisons.

Author: lX Drive Team
Version: 2.0.0
"""

import asyncio
import aiosqlite
import threading
import time
import hashlib
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from loguru import logger


@dataclass
class FileRecord:
    """Represents a synced file in the metadata store"""
    file_id: str
    account_id: str
    pair_id: str
    name: str
    parent_id: str
    local_path: str
    remote_path: str
    md5_hash: Optional[str] = None
    size_bytes: int = 0
    is_cached: bool = False
    is_on_demand: bool = False
    last_sync: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileRecord":
        return cls(**data)


@dataclass
class MoveEvent:
    """Represents a detected move operation"""
    file_id: str
    old_parent_id: str
    new_parent_id: str
    old_name: str
    new_name: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass  
class ChangeEvent:
    """Represents a remote change detected via API"""
    file_id: str
    change_id: int
    is_removed: bool = False
    is_new: bool = False
    name: Optional[str] = None
    parent_id: Optional[str] = None
    previous_parents: List[str] = field(default_factory=list)
    md5_hash: Optional[str] = None
    size_bytes: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class MetadataStore:
    """
    SQLite-based metadata store for Google Drive file tracking.
    
    Key Features:
    - Persistent file_id tracking across sessions
    - Fast lookups by file_id, local_path, or parent_id
    - Automatic backup every 24 hours
    - Corruption detection and recovery
    - Thread-safe async operations
    
    Schema:
        files(id, file_id UNIQUE, account_id, pair_id, parent_id, name, 
              local_path, remote_path, md5_hash, size_bytes, is_cached, 
              is_on_demand, last_sync, created_at, updated_at)
        
        sync_state(id, account_id, pair_id, last_change_id, last_sync)
        
        backups(id, timestamp, checksum, data)
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the metadata store.
        
        Args:
            db_path: Path to SQLite database. Defaults to ~/.config/lxdrive/metadata.db
        """
        if db_path is None:
            db_path = Path.home() / ".config" / "lxdrive" / "metadata.db"
        
        self.db_path = Path(db_path)
        self.db_dir = self.db_path.parent
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = threading.Lock()
        self._backup_lock = threading.Lock()
        self._last_backup_time = 0
        self._backup_interval = 86400  # 24 hours in seconds
        
        self._ensure_db_dir()
    
    def _ensure_db_dir(self):
        """Ensure the database directory exists"""
        self.db_dir.mkdir(parents=True, exist_ok=True)
    
    async def connect(self):
        """Connect to the SQLite database"""
        if self._db is not None:
            return
        
        self._db = await aiosqlite.connect(str(self.db_path))
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.execute("PRAGMA cache_size=-64000")
        await self._init_schema()
        logger.info(f"MetadataStore connected: {self.db_path}")
    
    async def close(self):
        """Close the database connection"""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("MetadataStore closed")
    
    async def _init_schema(self):
        """Initialize database schema"""
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE NOT NULL,
                account_id TEXT NOT NULL,
                pair_id TEXT NOT NULL,
                parent_id TEXT,
                name TEXT NOT NULL,
                local_path TEXT,
                remote_path TEXT,
                md5_hash TEXT,
                size_bytes INTEGER DEFAULT 0,
                is_cached BOOLEAN DEFAULT 0,
                is_on_demand BOOLEAN DEFAULT 0,
                last_sync TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id),
                FOREIGN KEY (pair_id) REFERENCES sync_pairs(id)
            );
            
            CREATE TABLE IF NOT EXISTS sync_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL UNIQUE,
                pair_id TEXT NOT NULL,
                last_change_id INTEGER DEFAULT 0,
                last_sync TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id),
                FOREIGN KEY (pair_id) REFERENCES sync_pairs(id)
            );
            
            CREATE TABLE IF NOT EXISTS cache_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair_id TEXT NOT NULL UNIQUE,
                total_size_bytes INTEGER DEFAULT 0,
                file_count INTEGER DEFAULT 0,
                last_cleanup TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_file_id ON files(file_id);
            CREATE INDEX IF NOT EXISTS idx_account_pair ON files(account_id, pair_id);
            CREATE INDEX IF NOT EXISTS idx_parent ON files(parent_id);
            CREATE INDEX IF NOT EXISTS idx_local_path ON files(pair_id, local_path);
            CREATE INDEX IF NOT EXISTS idx_sync_state_account ON sync_state(account_id);
        """)
        await self._db.commit()
        logger.debug("MetadataStore schema initialized")
    
    async def get_by_file_id(self, file_id: str) -> Optional[FileRecord]:
        """
        Get a file record by its Google Drive file_id.
        
        This is the primary method for detecting moves/renames.
        
        Args:
            file_id: Google Drive file_id
            
        Returns:
            FileRecord if found, None otherwise
        """
        async with self._db.execute(
            "SELECT * FROM files WHERE file_id = ?", (file_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_file_record(row)
            return None
    
    async def get_by_local_path(self, pair_id: str, local_path: str) -> Optional[FileRecord]:
        """
        Get a file record by its local path.
        
        Args:
            pair_id: SyncPair ID
            local_path: Relative path from sync pair root
            
        Returns:
            FileRecord if found, None otherwise
        """
        async with self._db.execute(
            "SELECT * FROM files WHERE pair_id = ? AND local_path = ?", 
            (pair_id, local_path)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_file_record(row)
            return None
    
    async def get_by_pair(self, pair_id: str) -> List[FileRecord]:
        """
        Get all file records for a sync pair.
        
        Args:
            pair_id: SyncPair ID
            
        Returns:
            List of FileRecord objects
        """
        async with self._db.execute(
            "SELECT * FROM files WHERE pair_id = ?", (pair_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_file_record(row) for row in rows]
    
    async def get_by_parent(self, parent_id: str) -> List[FileRecord]:
        """
        Get all files in a folder.
        
        Args:
            parent_id: Google Drive folder ID
            
        Returns:
            List of FileRecord objects
        """
        async with self._db.execute(
            "SELECT * FROM files WHERE parent_id = ?", (parent_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_file_record(row) for row in rows]
    
    async def upsert(self, record: FileRecord) -> bool:
        """
        Insert or update a file record.
        
        Uses file_id as the unique key. If file_id exists, updates the record.
        If file_id is new, inserts a new record.
        
        Args:
            record: FileRecord to save
            
        Returns:
            True if successful
        """
        now = datetime.now().isoformat()
        record.updated_at = now
        
        await self._db.execute("""
            INSERT INTO files (
                file_id, account_id, pair_id, parent_id, name,
                local_path, remote_path, md5_hash, size_bytes,
                is_cached, is_on_demand, last_sync, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                parent_id = excluded.parent_id,
                name = excluded.name,
                local_path = excluded.local_path,
                remote_path = excluded.remote_path,
                md5_hash = excluded.md5_hash,
                size_bytes = excluded.size_bytes,
                is_cached = excluded.is_cached,
                is_on_demand = excluded.is_on_demand,
                last_sync = excluded.last_sync,
                updated_at = excluded.updated_at
        """, (
            record.file_id, record.account_id, record.pair_id,
            record.parent_id, record.name, record.local_path,
            record.remote_path, record.md5_hash, record.size_bytes,
            record.is_cached, record.is_on_demand, record.last_sync,
            record.updated_at
        ))
        await self._db.commit()
        return True
    
    async def upsert_batch(self, records: List[FileRecord]) -> int:
        """
        Insert or update multiple file records in a single transaction.
        
        Args:
            records: List of FileRecord objects
            
        Returns:
            Number of records processed
        """
        if not records:
            return 0
        
        now = datetime.now().isoformat()
        
        for record in records:
            record.updated_at = now
        
        await self._db.executemany("""
            INSERT OR REPLACE INTO files (
                file_id, account_id, pair_id, parent_id, name,
                local_path, remote_path, md5_hash, size_bytes,
                is_cached, is_on_demand, last_sync, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [(
            r.file_id, r.account_id, r.pair_id, r.parent_id, r.name,
            r.local_path, r.remote_path, r.md5_hash, r.size_bytes,
            r.is_cached, r.is_on_demand, r.last_sync, r.updated_at
        ) for r in records])
        await self._db.commit()
        
        count = len(records)
        logger.debug(f"Batch upserted {count} records")
        return count
    
    async def delete(self, file_id: str) -> bool:
        """
        Delete a file record.
        
        Args:
            file_id: Google Drive file_id to delete
            
        Returns:
            True if deleted, False if not found
        """
        cursor = await self._db.execute(
            "DELETE FROM files WHERE file_id = ?", (file_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0
    
    async def delete_by_pair(self, pair_id: str) -> int:
        """
        Delete all file records for a sync pair.
        
        Args:
            pair_id: SyncPair ID
            
        Returns:
            Number of records deleted
        """
        cursor = await self._db.execute(
            "DELETE FROM files WHERE pair_id = ?", (pair_id,)
        )
        await self._db.commit()
        logger.info(f"Deleted {cursor.rowcount} records for pair {pair_id}")
        return cursor.rowcount
    
    async def delete_orphaned(self, pair_id: str, valid_file_ids: List[str]) -> int:
        """
        Delete file records that no longer exist in Google Drive.
        
        Args:
            pair_id: SyncPair ID
            valid_file_ids: List of file_ids that still exist
            
        Returns:
            Number of orphaned records deleted
        """
        if not valid_file_ids:
            # If no valid file_ids provided, delete all
            return await self.delete_by_pair(pair_id)
        
        placeholders = ",".join("?" * len(valid_file_ids))
        cursor = await self._db.execute(
            f"DELETE FROM files WHERE pair_id = ? AND file_id NOT IN ({placeholders})",
            [pair_id] + valid_file_ids
        )
        await self._db.commit()
        
        if cursor.rowcount > 0:
            logger.info(f"Cleaned {cursor.rowcount} orphaned records for pair {pair_id}")
        return cursor.rowcount
    
    async def detect_move(self, file_id: str, new_parent_id: str, new_name: str) -> Optional[MoveEvent]:
        """
        Detect if a file has been moved based on file_id and parent changes.
        
        This is the key method that replaces heuristic-based rename detection.
        
        Args:
            file_id: Google Drive file_id
            new_parent_id: New parent folder ID (from API)
            new_name: New name (from API)
            
        Returns:
            MoveEvent if a move was detected, None otherwise
        """
        record = await self.get_by_file_id(file_id)
        
        if record is None:
            # File doesn't exist in our database - might be a new file
            return None
        
        # Check if parent changed
        if record.parent_id != new_parent_id:
            # MOVED to a different folder
            return MoveEvent(
                file_id=file_id,
                old_parent_id=record.parent_id,
                new_parent_id=new_parent_id,
                old_name=record.name,
                new_name=new_name
            )
        
        # Check if name changed (rename within same folder)
        if record.name != new_name:
            # RENAMED in place
            return MoveEvent(
                file_id=file_id,
                old_parent_id=record.parent_id,
                new_parent_id=record.parent_id,
                old_name=record.name,
                new_name=new_name
            )
        
        return None
    
    async def get_file_ids_by_pair(self, pair_id: str) -> List[str]:
        """
        Get all file_ids for a sync pair.
        
        Useful for detecting orphaned records.
        
        Args:
            pair_id: SyncPair ID
            
        Returns:
            List of file_ids
        """
        async with self._db.execute(
            "SELECT file_id FROM files WHERE pair_id = ?", (pair_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    async def get_file_ids_all(self) -> List[str]:
        """
        Get all file_ids in the database.
        
        Returns:
            List of all file_ids
        """
        async with self._db.execute("SELECT file_id FROM files") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    async def get_count_by_pair(self, pair_id: str) -> int:
        """
        Get the number of files tracked for a sync pair.
        
        Args:
            pair_id: SyncPair ID
            
        Returns:
            File count
        """
        async with self._db.execute(
            "SELECT COUNT(*) FROM files WHERE pair_id = ?", (pair_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    async def get_total_size_by_pair(self, pair_id: str) -> int:
        """
        Get total cached size for a sync pair.
        
        Args:
            pair_id: SyncPair ID
            
        Returns:
            Total size in bytes
        """
        async with self._db.execute(
            "SELECT COALESCE(SUM(size_bytes), 0) FROM files WHERE pair_id = ? AND is_on_demand = 0",
            (pair_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    async def update_hash(self, file_id: str, md5_hash: str) -> bool:
        """
        Update the MD5 hash for a file.
        
        Args:
            file_id: Google Drive file_id
            md5_hash: New MD5 hash
            
        Returns:
            True if updated
        """
        await self._db.execute(
            "UPDATE files SET md5_hash = ?, updated_at = ? WHERE file_id = ?",
            (md5_hash, datetime.now().isoformat(), file_id)
        )
        await self._db.commit()
        return True
    
    async def update_local_path(self, file_id: str, local_path: str) -> bool:
        """
        Update the local path for a file.
        
        Useful after local moves.
        
        Args:
            file_id: Google Drive file_id
            local_path: New local path (relative to sync pair)
            
        Returns:
            True if updated
        """
        await self._db.execute(
            "UPDATE files SET local_path = ?, updated_at = ? WHERE file_id = ?",
            (local_path, datetime.now().isoformat(), file_id)
        )
        await self._db.commit()
        return True
    
    async def set_cached(self, file_id: str, is_cached: bool) -> bool:
        """
        Set the cached status for a file.
        
        Args:
            file_id: Google Drive file_id
            is_cached: Whether the file is cached locally
            
        Returns:
            True if updated
        """
        await self._db.execute(
            "UPDATE files SET is_cached = ?, updated_at = ? WHERE file_id = ?",
            (is_cached, datetime.now().isoformat(), file_id)
        )
        await self._db.commit()
        return True
    
    async def set_on_demand(self, file_id: str, is_on_demand: bool) -> bool:
        """
        Set the on-demand status for a file.
        
        Args:
            file_id: Google Drive file_id
            is_on_demand: Whether the file is on-demand (>10GB)
            
        Returns:
            True if updated
        """
        await self._db.execute(
            "UPDATE files SET is_on_demand = ?, updated_at = ? WHERE file_id = ?",
            (is_on_demand, datetime.now().isoformat(), file_id)
        )
        await self._db.commit()
        return True
    
    # Sync State Management
    
    async def get_sync_state(self, account_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the sync state for an account.
        
        Stores the last_change_id for incremental syncs.
        
        Args:
            account_id: Account ID
            
        Returns:
            Sync state dict or None
        """
        async with self._db.execute(
            "SELECT * FROM sync_state WHERE account_id = ?", (account_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "account_id": row[1],
                    "pair_id": row[2],
                    "last_change_id": row[3],
                    "last_sync": row[4],
                    "updated_at": row[5]
                }
            return None
    
    async def set_sync_state(self, account_id: str, pair_id: str, 
                            last_change_id: int, last_sync: Optional[str] = None) -> bool:
        """
        Set the sync state for an account.
        
        Args:
            account_id: Account ID
            pair_id: SyncPair ID
            last_change_id: Last processed change ID from Drive API
            last_sync: Last sync timestamp
            
        Returns:
            True if successful
        """
        now = datetime.now().isoformat()
        await self._db.execute("""
            INSERT INTO sync_state (account_id, pair_id, last_change_id, last_sync, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET
                pair_id = excluded.pair_id,
                last_change_id = excluded.last_change_id,
                last_sync = excluded.last_sync,
                updated_at = excluded.updated_at
        """, (account_id, pair_id, last_change_id, last_sync, now))
        await self._db.commit()
        return True
    
    async def increment_change_id(self, account_id: str) -> int:
        """
        Increment the change ID for an account (for polling).
        
        Args:
            account_id: Account ID
            
        Returns:
            New change ID
        """
        state = await self.get_sync_state(account_id)
        new_id = (state["last_change_id"] if state else 0) + 1
        await self.set_sync_state(
            account_id, 
            state["pair_id"] if state else "", 
            new_id
        )
        return new_id
    
    # Backup and Recovery
    
    async def backup(self) -> bool:
        """
        Create a backup of the database.
        
        Called automatically every 24 hours.
        
        Returns:
            True if backup created
        """
        if not self._backup_lock.acquire(blocking=False):
            logger.debug("Backup already in progress, skipping")
            return False
        
        try:
            backup_path = self.db_path.with_suffix(".backup")
            
            # Create backup using online backup API
            await self._db.execute(f"VACUUM INTO '{backup_path}'")
            
            # Verify backup integrity
            backup_size = backup_path.stat().st_size
            original_size = self.db_path.stat().st_size
            
            if backup_size > original_size * 0.9:  # Backup should be similar size
                # Rename old backup
                old_backup = self.db_path.with_suffix(".old")
                if old_backup.exists():
                    old_backup.unlink()
                if self.db_path.with_suffix(".backup").exists():
                    self.db_path.with_suffix(".backup").rename(old_backup)
                
                # Move new backup to main location
                backup_path.rename(self.db_path.with_suffix(".backup"))
                
                self._last_backup_time = time.time()
                logger.info(f"Backup created: {self.db_path.with_suffix('.backup')}")
                return True
            else:
                logger.warning(f"Backup verification failed: size mismatch")
                if backup_path.exists():
                    backup_path.unlink()
                return False
                
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False
        finally:
            self._backup_lock.release()
    
    async def restore(self) -> bool:
        """
        Restore from backup if main database is corrupted.
        
        Returns:
            True if restored successfully
        """
        backup_path = self.db_path.with_suffix(".backup")
        
        if not backup_path.exists():
            logger.warning("No backup found to restore")
            return False
        
        try:
            # Close current connection
            await self.close()
            
            # Rename corrupted db
            corrupted = self.db_path.with_suffix(".corrupted")
            if self.db_path.exists():
                self.db_path.rename(corrupted)
            
            # Restore from backup
            backup_path.rename(self.db_path)
            
            # Reconnect
            await self.connect()
            
            logger.info("Restored from backup successfully")
            return True
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
    
    async def check_integrity(self) -> Tuple[bool, str]:
        """
        Check database integrity.
        
        Returns:
            (is_valid, message)
        """
        try:
            async with self._db.execute("PRAGMA integrity_check") as cursor:
                result = await cursor.fetchone()
                if result and result[0] == "ok":
                    return True, "Database integrity OK"
                else:
                    return False, f"Integrity check failed: {result}"
        except Exception as e:
            return False, f"Integrity check error: {e}"
    
    async def rebuild_from_api(self, account_id: str, pair_id: str,
                               api_files: List[Dict[str, Any]]) -> int:
        """
        Rebuild metadata from Google Drive API response.
        
        Used when cache is corrupted or lost.
        
        Args:
            account_id: Account ID
            pair_id: SyncPair ID  
            api_files: List of file metadata from Drive API
            
        Returns:
            Number of records created
        """
        records = []
        now = datetime.now().isoformat()
        
        for f in api_files:
            # Determine if file should be cached or on-demand
            size = f.get("size", 0)
            is_on_demand = size > (10 * 1024**3)  # >10GB
            
            record = FileRecord(
                file_id=f["id"],
                account_id=account_id,
                pair_id=pair_id,
                parent_id=f.get("parents", [None])[0] if f.get("parents") else None,
                name=f["name"],
                local_path="",  # Will be set during sync
                remote_path="",  # Will be set during sync
                md5_hash=f.get("md5Checksum"),
                size_bytes=size,
                is_cached=not is_on_demand,
                is_on_demand=is_on_demand,
                last_sync=now
            )
            records.append(record)
        
        # Clear old records and insert new
        await self.delete_by_pair(pair_id)
        await self.upsert_batch(records)
        
        count = len(records)
        logger.info(f"Rebuilt {count} records from API for pair {pair_id}")
        return count
    
    def _row_to_file_record(self, row: Tuple) -> FileRecord:
        """Convert a database row to FileRecord"""
        return FileRecord(
            file_id=row[1],
            account_id=row[2],
            pair_id=row[3],
            parent_id=row[4],
            name=row[5],
            local_path=row[6] or "",
            remote_path=row[7] or "",
            md5_hash=row[8],
            size_bytes=row[9],
            is_cached=bool(row[10]),
            is_on_demand=bool(row[11]),
            last_sync=row[12],
            created_at=row[13],
            updated_at=row[14]
        )
    
    async def vacuum(self):
        """Optimize database after bulk operations"""
        await self._db.execute("VACUUM")
        logger.debug("Database vacuumed")


# Utility functions

def calculate_md5(file_path: Path, chunk_size: int = 8192) -> str:
    """
    Calculate MD5 hash of a file.
    
    Args:
        file_path: Path to file
        chunk_size: Read chunk size
        
    Returns:
        MD5 hex string
    """
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            md5.update(chunk)
    return md5.hexdigest()


async def create_metadata_store(db_path: Optional[Path] = None) -> MetadataStore:
    """
    Factory function to create and initialize a MetadataStore.
    
    Args:
        db_path: Optional database path
        
    Returns:
        Initialized MetadataStore instance
    """
    store = MetadataStore(db_path)
    await store.connect()
    return store
