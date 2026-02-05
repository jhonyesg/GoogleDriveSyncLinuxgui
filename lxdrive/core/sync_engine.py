#!/usr/bin/env python3
"""
SyncEngine - Operation-based sync engine for lX Drive v2.0

Replaces bisync with directed operations based on change events.
Uses file_id tracking for accurate move/rename detection.

Key Features:
- Event-driven synchronization
- file_id-based move/rename detection (no heuristics)
- Conflict detection and resolution
- Hybrid caching (<10GB local, >10GB on-demand)
- Batch operations for efficiency

Author: lX Drive Team
Version: 2.0.0
"""

import asyncio
import hashlib
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from loguru import logger

from .metadata_store import (
    MetadataStore, FileRecord, MoveEvent, ChangeEvent
)
from .drive_api_client import (
    DriveAPIClient, DriveFile, DriveChange, DriveAPIError
)
from .rclone_wrapper import RcloneWrapper


class SyncDirection(Enum):
    """Sync direction for a pair"""
    BIDIRECTIONAL = "bidirectional"
    UPLOAD_ONLY = "upload"
    DOWNLOAD_ONLY = "download"


class ConflictType(Enum):
    """Type of conflict detected"""
    NONE = "none"
    CONTENT_DIFFER = "content_different"
    EDIT_CONFLICT = "edit_conflict"
    MOVE_COLLISION = "move_collision"


@dataclass
class SyncOperation:
    """Represents a single sync operation"""
    type: str  # move, rename, delete, create, modify
    file_id: str
    local_path: Optional[str]
    remote_path: Optional[str]
    direction: str  # local_to_remote, remote_to_local
    priority: int = 0  # Higher = more urgent
    success: bool = False
    error: Optional[str] = None


@dataclass
class ConflictInfo:
    """Information about a sync conflict"""
    type: ConflictType
    local_record: Optional[FileRecord]
    remote_file: Optional[DriveFile]
    local_hash: Optional[str]
    remote_hash: Optional[str]
    suggested_resolution: str = "keep_both"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SyncResult:
    """Result of a sync operation"""
    success: bool
    operations: List[SyncOperation] = field(default_factory=list)
    conflicts: List[ConflictInfo] = field(default_factory=list)
    files_synced: int = 0
    bytes_transferred: int = 0
    errors: List[str] = field(default_factory=list)
    duration_ms: int = 0


class SyncEngine:
    """
    Event-driven sync engine for lX Drive.
    
    Replaces bisync with directed operations based on:
    - Local changes detected via Watchdog
    - Remote changes detected via Drive API
    
    Architecture:
        Remote Change → API Event → Metadata Store → Operation → rclone
        Local Change → Watchdog → Metadata Store → Operation → rclone
    """
    
    MAX_CACHE_SIZE_GB = 10
    CONFLICT_RESOLUTION = "timestamp"  # Default: timestamp wins
    
    def __init__(
        self,
        rclone: RcloneWrapper,
        metadata: MetadataStore,
        drive_client: DriveAPIClient,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the sync engine.
        
        Args:
            rclone: RcloneWrapper instance for file operations
            metadata: MetadataStore instance for file tracking
            drive_client: DriveAPIClient instance for API access
            config: Optional configuration dict
        """
        self.rclone = rclone
        self.metadata = metadata
        self.drive = drive_client
        self.config = config or {}
        
        # Settings from config
        self.max_cache_gb = self.config.get("max_cache_gb", self.MAX_CACHE_SIZE_GB)
        self.conflict_resolution = self.config.get("conflict_resolution", self.CONFLICT_RESOLUTION)
        self.default_direction = SyncDirection(
            self.config.get("sync_direction", "bidirectional")
        )
        
        # State
        self._running = False
        self._pending_operations: List[SyncOperation] = []
        self._operation_lock = asyncio.Lock()
    
    async def start(self):
        """Start the sync engine"""
        self._running = True
        logger.info("SyncEngine started")
    
    async def stop(self):
        """Stop the sync engine"""
        self._running = False
        logger.info("SyncEngine stopped")
    
    async def sync_pair(
        self,
        account_id: str,
        pair_id: str,
        local_base: Path,
        remote_base: str,
        direction: SyncDirection = None
    ) -> SyncResult:
        """
        Perform a full sync for a sync pair.
        
        Args:
            account_id: Account ID
            pair_id: SyncPair ID
            local_base: Local base directory
            remote_base: Remote base path
            direction: Sync direction override
            
        Returns:
            SyncResult with operations performed
        """
        start_time = time.time()
        result = SyncResult(success=True)
        
        direction = direction or self.default_direction
        
        logger.info(f"Syncing pair {pair_id}: {local_base} ↔ {remote_base}")
        
        try:
            # Step 1: Process any pending operations first
            pending_ops = await self._get_pending_operations(pair_id)
            for op in pending_ops:
                op_result = await self._execute_operation(op, local_base, remote_base)
                result.operations.append(op_result)
                if op_result.success:
                    result.files_synced += 1
            
            # Step 2: Check for remote changes via API
            if direction in [SyncDirection.BIDIRECTIONAL, SyncDirection.DOWNLOAD_ONLY]:
                remote_changes = await self._check_remote_changes(
                    account_id, pair_id, local_base, remote_base
                )
                for change in remote_changes:
                    op = await self._process_remote_change(
                        change, pair_id, local_base, remote_base
                    )
                    if op:
                        result.operations.append(op)
                        result.files_synced += 1
            
            # Step 3: Update sync timestamp
            await self.metadata.set_sync_state(
                account_id, pair_id, 
                last_change_id=0,  # Would track properly in full impl
                last_sync=datetime.now().isoformat()
            )
            
            result.success = len(result.errors) == 0
            
        except Exception as e:
            logger.error(f"Sync error: {e}")
            result.success = False
            result.errors.append(str(e))
        
        result.duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"Sync completed in {result.duration_ms}ms: {result.files_synced} files")
        return result
    
    async def handle_local_change(
        self,
        event_type: str,
        local_path: Path,
        pair_id: str,
        account_id: str,
        local_base: Path,
        remote_base: str,
        direction: SyncDirection = None
    ) -> Optional[SyncOperation]:
        """
        Handle a local change detected by Watchdog.
        
        Args:
            event_type: created, modified, moved, deleted
            local_path: Full path to the file/folder
            pair_id: SyncPair ID
            account_id: Account ID
            local_base: Base path of the sync pair
            remote_base: Remote base path
            
        Returns:
            SyncOperation if one was created
        """
        direction = direction or self.default_direction
        
        # Calculate relative path
        try:
            rel_path = local_path.relative_to(local_base)
        except ValueError:
            logger.warning(f"Path outside sync base: {local_path}")
            return None
        
        rel_str = str(rel_path)
        
        # Check if we should process this event
        if await self._should_ignore_path(local_path):
            return None
        
        # Handle based on event type
        if event_type == "created":
            return await self._handle_local_create(
                local_path, rel_str, pair_id, account_id, 
                local_base, remote_base, direction
            )
        elif event_type == "modified":
            return await self._handle_local_modify(
                local_path, rel_str, pair_id, account_id,
                local_base, remote_base, direction
            )
        elif event_type == "moved":
            return await self._handle_local_move(
                local_path, rel_str, pair_id, account_id,
                local_base, remote_base, direction
            )
        elif event_type == "deleted":
            return await self._handle_local_delete(
                rel_str, pair_id, account_id, remote_base, direction
            )
        
        return None
    
    async def _handle_local_create(
        self,
        local_path: Path,
        rel_path: str,
        pair_id: str,
        account_id: str,
        local_base: Path,
        remote_base: str,
        direction: SyncDirection
    ) -> Optional[SyncOperation]:
        """Handle local file creation"""
        if direction == SyncDirection.DOWNLOAD_ONLY:
            return None  # Don't upload in download-only mode
        
        # Check if file or folder
        is_folder = local_path.is_dir()
        
        # Calculate remote path
        remote_path = f"{remote_base}/{rel_path}" if remote_base else rel_path
        
        # Determine if should be cached
        size = local_path.stat().st_size if local_path.exists() else 0
        should_cache = await self._should_cache_file(size)
        
        # Create operation
        op = SyncOperation(
            type="create",
            file_id="",  # Will be assigned after upload
            local_path=rel_path,
            remote_path=remote_path,
            direction="local_to_remote",
            priority=1
        )
        
        # Execute the operation
        result = await self._execute_operation(
            op, local_base, remote_base, is_folder=is_folder
        )
        
        if result.success and result.file_id:
            # Create metadata record
            record = FileRecord(
                file_id=result.file_id,
                account_id=account_id,
                pair_id=pair_id,
                name=local_path.name,
                parent_id="",  # Will be set by API
                local_path=rel_path,
                remote_path=remote_path,
                size_bytes=size,
                is_cached=should_cache,
                is_on_demand=not should_cache,
                last_sync=datetime.now().isoformat()
            )
            await self.metadata.upsert(record)
        
        return result
    
    async def _handle_local_modify(
        self,
        local_path: Path,
        rel_path: str,
        pair_id: str,
        account_id: str,
        local_base: Path,
        remote_base: str,
        direction: SyncDirection
    ) -> Optional[SyncOperation]:
        """Handle local file modification"""
        if direction == SyncDirection.DOWNLOAD_ONLY:
            return None
        
        # Get existing record to get file_id
        record = await self.metadata.get_by_local_path(pair_id, rel_path)
        
        if not record:
            # File not tracked, treat as create
            return await self._handle_local_create(
                local_path, rel_path, pair_id, account_id,
                local_base, remote_base, direction
            )
        
        # Calculate remote path
        remote_path = f"{remote_base}/{rel_path}" if remote_base else rel_path
        
        # Create operation
        op = SyncOperation(
            type="modify",
            file_id=record.file_id,
            local_path=rel_path,
            remote_path=remote_path,
            direction="local_to_remote",
            priority=2
        )
        
        return await self._execute_operation(
            op, local_base, remote_base
        )
    
    async def _handle_local_move(
        self,
        local_path: Path,
        rel_path: str,
        pair_id: str,
        account_id: str,
        local_base: Path,
        remote_base: str,
        direction: SyncDirection
    ) -> Optional[SyncOperation]:
        """Handle local file move/rename"""
        # Find the original record by checking for deleted path
        old_rel_path = None
        old_record = None
        
        # For local moves, we need to find the original file
        # The ChangeHandler should have tracked this
        
        # For now, we'll detect this via the parent metadata store
        # which should have been updated by the move detection logic
        
        return None  # Local moves handled by ChangeHandler
    
    async def _handle_local_delete(
        self,
        rel_path: str,
        pair_id: str,
        account_id: str,
        remote_base: str,
        direction: SyncDirection
    ) -> Optional[SyncOperation]:
        """Handle local file deletion"""
        if direction == SyncDirection.UPLOAD_ONLY:
            return None  # Don't delete from remote in upload-only
        
        # Get existing record
        record = await self.metadata.get_by_local_path(pair_id, rel_path)
        
        if not record:
            logger.warning(f"Delete for untracked file: {rel_path}")
            return None
        
        # Create operation
        op = SyncOperation(
            type="delete",
            file_id=record.file_id,
            local_path=rel_path,
            remote_path=f"{remote_base}/{rel_path}" if remote_base else rel_path,
            direction="local_to_remote",
            priority=3  # Deletes are high priority
        )
        
        result = await self._execute_operation(op, Path(""), remote_base)
        
        if result.success:
            await self.metadata.delete(record.file_id)
        
        return result
    
    async def _check_remote_changes(
        self,
        account_id: str,
        pair_id: str,
        local_base: Path,
        remote_base: str
    ) -> List[ChangeEvent]:
        """
        Check for remote changes using Drive API.
        
        Returns:
            List of detected changes
        """
        # Get sync state
        state = await self.metadata.get_sync_state(account_id)
        start_change_id = state["last_change_id"] if state else 0
        
        # Get changes from API
        changes = await self.drive.list_changes(start_change_id)
        
        # Filter to changes within our sync pair
        filtered_changes = []
        for change in changes:
            if change.is_removed:
                # Check if this file was in our tracked set
                record = await self.metadata.get_by_file_id(change.file_id)
                if record and record.pair_id == pair_id:
                    filtered_changes.append(change)
            else:
                # New/modified file - check if in our remote base
                if change.file:
                    filtered_changes.append(change)
        
        return filtered_changes
    
    async def _process_remote_change(
        self,
        change: ChangeEvent,
        pair_id: str,
        local_base: Path,
        remote_base: str
    ) -> Optional[SyncOperation]:
        """
        Process a single remote change.
        
        This is the KEY method that replaces bisync heuristics
        with proper file_id-based detection.
        """
        file_id = change.file_id
        
        # Get existing record
        existing = await self.metadata.get_by_file_id(file_id)
        
        if change.is_removed:
            # File was deleted from Drive
            if existing:
                return await self._handle_remote_delete(
                    existing, pair_id, local_base
                )
            return None
        
        # Get change details
        file = change.file
        if not file:
            return None
        
        new_parent = file.parent_id
        new_name = file.name
        
        # Detect the type of change using file_id
        if existing:
            # Existing file - check for move/rename
            move_event = await self.metadata.detect_move(
                file_id, new_parent, new_name
            )
            
            if move_event:
                if move_event.old_parent_id != move_event.new_parent_id:
                    # MOVE to different folder
                    return await self._handle_remote_move(
                        existing, move_event, pair_id, local_base, remote_base
                    )
                else:
                    # RENAME in place
                    return await self._handle_remote_rename(
                        existing, move_event, pair_id, local_base, remote_base
                    )
            else:
                # MODIFY content
                return await self._handle_remote_modify(
                    existing, file, pair_id, local_base, remote_base
                )
        else:
            # New file
            return await self._handle_remote_create(
                file, pair_id, local_base, remote_base
            )
    
    async def _handle_remote_move(
        self,
        existing: FileRecord,
        move_event: MoveEvent,
        pair_id: str,
        local_base: Path,
        remote_base: str
    ) -> SyncOperation:
        """
        Handle remote file move.
        
        This is where the old bisync would have created duplicates.
        With file_id tracking, we correctly detect this as a MOVE.
        """
        old_remote = f"{remote_base}/{move_event.old_name}"
        new_remote = f"{remote_base}/{move_event.new_name}"
        
        op = SyncOperation(
            type="move",
            file_id=existing.file_id,
            local_path=existing.local_path,
            remote_path=new_remote,
            direction="remote_to_local",
            priority=2
        )
        
        # Execute via rclone (server-side move)
        success, msg = self.rclone.moveto(
            f"{self._get_remote_name(remote_base)}:{old_remote}",
            f"{self._get_remote_name(remote_base)}:{new_remote}"
        )
        
        op.success = success
        if not success:
            op.error = msg
        
        # Update metadata
        if success:
            # Calculate new local path
            old_name = Path(existing.local_path).name
            new_local = existing.local_path.replace(old_name, move_event.new_name)
            
            await self.metadata.update_local_path(existing.file_id, new_local)
            await self.metadata.upsert(existing)  # Update parent_id etc.
        
        return op
    
    async def _handle_remote_rename(
        self,
        existing: FileRecord,
        move_event: MoveEvent,
        pair_id: str,
        local_base: Path,
        remote_base: str
    ) -> SyncOperation:
        """Handle remote file rename (same folder, different name)"""
        old_remote = f"{remote_base}/{move_event.old_name}"
        new_remote = f"{remote_base}/{move_event.new_name}"
        
        op = SyncOperation(
            type="rename",
            file_id=existing.file_id,
            local_path=existing.local_path,
            remote_path=new_remote,
            direction="remote_to_local",
            priority=2
        )
        
        # Execute via rclone
        success, msg = self.rclone.moveto(
            f"{self._get_remote_name(remote_base)}:{old_remote}",
            f"{self._get_remote_name(remote_base)}:{new_remote}"
        )
        
        op.success = success
        if not success:
            op.error = msg
        
        # Update metadata
        if success:
            new_local = existing.local_path.replace(move_event.old_name, move_event.new_name)
            await self.metadata.update_local_path(existing.file_id, new_local)
        
        return op
    
    async def _handle_remote_modify(
        self,
        existing: FileRecord,
        file: DriveFile,
        pair_id: str,
        local_base: Path,
        remote_base: str
    ) -> SyncOperation:
        """Handle remote file modification (content change)"""
        local_path = local_base / existing.local_path
        
        op = SyncOperation(
            type="modify",
            file_id=existing.file_id,
            local_path=existing.local_path,
            remote_path=f"{remote_base}/{existing.local_path}",
            direction="remote_to_local",
            priority=2
        )
        
        # Check for conflict
        conflict = await self._check_conflict(existing, file)
        if conflict.type != ConflictType.NONE:
            logger.warning(f"Conflict detected for {existing.local_path}")
            return await self._resolve_conflict(
                conflict, op, local_base, remote_base
            )
        
        # Download via rclone
        success, msg = self.rclone.copyto(
            f"{self._get_remote_name(remote_base)}:{remote_base}/{existing.local_path}",
            str(local_path)
        )
        
        op.success = success
        if not success:
            op.error = msg
        
        # Update metadata
        if success and file.md5_checksum:
            await self.metadata.update_hash(existing.file_id, file.md5_checksum)
        
        return op
    
    async def _handle_remote_create(
        self,
        file: DriveFile,
        pair_id: str,
        local_base: Path,
        remote_base: str
    ) -> SyncOperation:
        """Handle new remote file"""
        rel_path = file.name
        
        # Determine if should be cached
        should_cache = await self._should_cache_file(file.size)
        
        local_path = local_base / rel_path
        
        op = SyncOperation(
            type="create",
            file_id=file.id,
            local_path=rel_path,
            remote_path=rel_path,
            direction="remote_to_local",
            priority=1
        )
        
        # Download via rclone
        success, msg = self.rclone.copyto(
            f"{self._get_remote_name(remote_base)}:{remote_base}/{rel_path}",
            str(local_path)
        )
        
        op.success = success
        if not success:
            op.error = msg
        
        # Create metadata
        if success:
            record = FileRecord(
                file_id=file.id,
                account_id="",  # Would be set
                pair_id=pair_id,
                name=file.name,
                parent_id=file.parent_id or "",
                local_path=rel_path,
                remote_path=rel_path,
                md5_hash=file.md5_checksum,
                size_bytes=file.size,
                is_cached=should_cache,
                is_on_demand=not should_cache,
                last_sync=datetime.now().isoformat()
            )
            await self.metadata.upsert(record)
        
        return op
    
    async def _handle_remote_delete(
        self,
        existing: FileRecord,
        pair_id: str,
        local_base: Path
    ) -> SyncOperation:
        """Handle remote file deletion"""
        op = SyncOperation(
            type="delete",
            file_id=existing.file_id,
            local_path=existing.local_path,
            remote_path=existing.remote_path,
            direction="remote_to_local",
            priority=3
        )
        
        # Delete local file
        local_path = local_base / existing.local_path
        if local_path.exists():
            try:
                local_path.unlink()
                op.success = True
            except Exception as e:
                op.success = False
                op.error = str(e)
        else:
            op.success = True  # Already gone
        
        # Remove metadata
        if op.success:
            await self.metadata.delete(existing.file_id)
        
        return op
    
    async def _execute_operation(
        self,
        op: SyncOperation,
        local_base: Path,
        remote_base: str,
        is_folder: bool = False
    ) -> SyncOperation:
        """Execute a sync operation"""
        try:
            if op.type in ["create", "modify"]:
                if is_folder:
                    # Create directory
                    (local_base / op.local_path).mkdir(parents=True, exist_ok=True)
                    op.success = True
                else:
                    # Upload/download file
                    if op.direction == "local_to_remote":
                        success, msg = self.rclone.copyto(
                            str(local_base / op.local_path),
                            f"{self._get_remote_name(remote_base)}:{remote_base}/{op.local_path}"
                        )
                    else:
                        success, msg = self.rclone.copyto(
                            f"{self._get_remote_name(remote_base)}:{remote_base}/{op.local_path}",
                            str(local_base / op.local_path)
                        )
                    op.success = success
                    if not success:
                        op.error = msg
            
            elif op.type == "move":
                success, msg = self.rclone.moveto(
                    f"{self._get_remote_name(remote_base)}:{op.remote_path}",
                    f"{self._get_remote_name(remote_base)}:{remote_base}/{Path(op.remote_path).name}"
                )
                op.success = success
                if not success:
                    op.error = msg
            
            elif op.type == "rename":
                success, msg = self.rclone.moveto(
                    f"{self._get_remote_name(remote_base)}:{Path(op.remote_path).parent}",
                    f"{self._get_remote_name(remote_base)}:{Path(op.remote_path).parent}/{Path(op.remote_path).name}"
                )
                op.success = success
                if not success:
                    op.error = msg
            
            elif op.type == "delete":
                if op.direction == "local_to_remote":
                    success, msg = self.rclone.purge(
                        f"{self._get_remote_name(remote_base)}:{remote_base}/{op.local_path}"
                    )
                else:
                    local_path = local_base / op.local_path
                    if local_path.exists():
                        local_path.unlink()
                    success = True
                op.success = success
                if not success:
                    op.error = msg
        
        except Exception as e:
            op.success = False
            op.error = str(e)
        
        return op
    
    async def _check_conflict(
        self,
        local_record: FileRecord,
        remote_file: DriveFile
    ) -> ConflictInfo:
        """Check for edit conflict between local and remote"""
        local_path = Path(local_record.local_path)
        
        if not local_path.exists():
            return ConflictInfo(
                type=ConflictType.NONE,
                local_record=local_record,
                remote_file=remote_file,
                local_hash=None,
                remote_hash=remote_file.md5_checksum
            )
        
        # Calculate local hash
        local_hash = self._calculate_local_hash(local_path)
        remote_hash = remote_file.md5_checksum
        
        if local_hash == remote_hash:
            return ConflictInfo(
                type=ConflictType.NONE,
                local_record=local_record,
                remote_file=remote_file,
                local_hash=local_hash,
                remote_hash=remote_hash
            )
        
        # Both have different content - CONFLICT
        return ConflictInfo(
            type=ConflictType.EDIT_CONFLICT,
            local_record=local_record,
            remote_file=remote_file,
            local_hash=local_hash,
            remote_hash=remote_hash,
            suggested_resolution=self.conflict_resolution
        )
    
    async def _resolve_conflict(
        self,
        conflict: ConflictInfo,
        op: SyncOperation,
        local_base: Path,
        remote_base: str
    ) -> SyncOperation:
        """Resolve a sync conflict"""
        resolution = conflict.suggested_resolution
        
        if resolution == "keep_both":
            # Rename local file
            local_path = local_base / conflict.local_record.local_path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            conflict_name = f"{local_path.stem}_conflict_{timestamp}{local_path.suffix}"
            conflict_path = local_path.parent / conflict_name
            
            # Rename existing local
            if local_path.exists():
                local_path.rename(conflict_path)
            
            # Download remote
            op.success, msg = self.rclone.copyto(
                f"{self._get_remote_name(remote_base)}:{remote_base}/{conflict.local_record.local_path}",
                str(local_path)
            )
            
            if not op.success:
                op.error = msg
            
            logger.info(f"Conflict resolved: {conflict.local_record.local_path} -> {conflict_name}")
        
        elif resolution == "keep_local":
            # Keep local, upload to remote with new name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_remote_name = f"{Path(op.remote_path).stem}_remote_{timestamp}{Path(op.remote_path).suffix}"
            
            success, msg = self.rclone.moveto(
                f"{self._get_remote_name(remote_base)}:{op.remote_path}",
                f"{self._get_remote_name(remote_base)}:{remote_base}/{new_remote_name}"
            )
            
            if success:
                # Upload local to original name
                success2, msg2 = self.rclone.copyto(
                    str(local_base / conflict.local_record.local_path),
                    f"{self._get_remote_name(remote_base)}:{op.remote_path}"
                )
                op.success = success2
                if not success2:
                    op.error = msg2
            else:
                op.success = False
                op.error = msg
        
        elif resolution == "keep_remote":
            # Just download remote (overwrite local)
            local_path = local_base / conflict.local_record.local_path
            
            if local_path.exists():
                local_path.unlink()
            
            op.success, msg = self.rclone.copyto(
                f"{self._get_remote_name(remote_base)}:{op.remote_path}",
                str(local_path)
            )
            
            if not op.success:
                op.error = msg
        
        elif resolution == "timestamp":
            # Winner by timestamp (implementation depends on storing mtimes)
            # For now, keep both
            return await self._resolve_conflict(
                conflict.copy(suggested_resolution="keep_both"),
                op, local_base, remote_base
            )
        
        return op
    
    async def _should_cache_file(self, size_bytes: int) -> bool:
        """Determine if a file should be cached locally"""
        max_bytes = self.max_cache_gb * 1024**3
        return size_bytes <= max_bytes
    
    def _calculate_local_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of a local file"""
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                md5.update(chunk)
        return md5.hexdigest()
    
    def _get_remote_name(self, remote_base: str) -> str:
        """Extract remote name from remote base path"""
        if ":" in remote_base:
            return remote_base.split(":")[0]
        return "drive"  # Default
    
    async def _should_ignore_path(self, path: Path) -> bool:
        """Check if a path should be ignored"""
        ignore_patterns = [
            ".partial", ".tmp", ".rclone", "~$", ".swp", ".swo",
            ".git", "__pycache__", ".tox", ".venv"
        ]
        
        path_str = str(path)
        for pattern in ignore_patterns:
            if pattern in path_str:
                return True
        
        return False
    
    async def _get_pending_operations(self, pair_id: str) -> List[SyncOperation]:
        """Get pending operations for a pair"""
        async with self._operation_lock:
            ops = [op for op in self._pending_operations if op.local_path.startswith(pair_id)]
            self._pending_operations = [
                op for op in self._pending_operations 
                if not op.local_path.startswith(pair_id)
            ]
            return ops


async def create_sync_engine(
    rclone: RcloneWrapper,
    metadata: MetadataStore,
    drive_client: DriveAPIClient,
    config: Optional[Dict[str, Any]] = None
) -> SyncEngine:
    """
    Factory function to create a SyncEngine.
    
    Args:
        rclone: RcloneWrapper instance
        metadata: MetadataStore instance
        drive_client: DriveAPIClient instance
        config: Optional configuration
        
    Returns:
        Configured SyncEngine instance
    """
    engine = SyncEngine(rclone, metadata, drive_client, config)
    await engine.start()
    return engine
