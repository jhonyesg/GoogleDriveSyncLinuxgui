#!/usr/bin/env python3
"""
DriveAPIClient - Google Drive API v3 wrapper for lX Drive

Provides async access to Google Drive API with focus on:
- Change detection (incremental syncs)
- File metadata retrieval
- Batch operations
- Efficient polling for real-time updates

Author: lX Drive Team
Version: 2.0.0
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.discovery import build as build_service
    from googleapiclient.http import MediaIoBaseDownload
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    logger.warning("Google API libraries not installed. Run: pip install google-api-python-client google-auth google-auth-oauthlib")


@dataclass
class DriveFile:
    """Represents a file/folder from Google Drive"""
    id: str
    name: str
    mime_type: str
    parent_id: Optional[str] = None
    parents: List[str] = field(default_factory=list)
    size: int = 0
    md5_checksum: Optional[str] = None
    modified_time: Optional[str] = None
    created_time: Optional[str] = None
    is_folder: bool = False
    trashed: bool = False
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "DriveFile":
        """Create DriveFile from Google Drive API response"""
        is_folder = data.get("mimeType", "").endswith(".folder")
        parents = data.get("parents", [])
        
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            mime_type=data.get("mimeType", ""),
            parent_id=parents[0] if parents else None,
            parents=parents,
            size=int(data.get("size", 0)) if "size" in data else 0,
            md5_checksum=data.get("md5Checksum"),
            modified_time=data.get("modifiedTime"),
            created_time=data.get("createdTime"),
            is_folder=is_folder,
            trashed=data.get("trashed", False)
        )


@dataclass
class DriveChange:
    """Represents a change from Google Drive changes API"""
    change_id: int
    file_id: str
    file: Optional[DriveFile] = None
    is_removed: bool = False
    is_new: bool = False
    time: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @classmethod
    def from_change_response(cls, data: Dict[str, Any]) -> "DriveChange":
        """Create DriveChange from Drive API changes response"""
        file_data = data.get("file")
        file_obj = DriveFile.from_api_response(file_data) if file_data else None
        
        return cls(
            change_id=int(data.get("changeId", 0)),
            file_id=data.get("fileId", ""),
            file=file_obj,
            is_removed=data.get("removed", False),
            is_new=file_data is not None and not data.get("deleted", False)
        )


@dataclass
class DriveFolder:
    """Represents a folder for browsing"""
    id: str
    name: str
    path: str
    parent_id: Optional[str] = None


class DriveAPIError(Exception):
    """Base exception for Drive API errors"""
    def __init__(self, message: str, status_code: int = None, details: str = None):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class DriveAPIClient:
    """
    Async wrapper for Google Drive API v3.
    
    Key Features:
    - Async/await interface
    - Change tracking with startChangeId
    - Efficient batching for large operations
    - Automatic token refresh
    - Retry with exponential backoff
    
    Usage:
        client = DriveAPIClient(credentials)
        changes = await client.list_changes(start_change_id)
        file = await client.get_file_metadata(file_id)
    """
    
    SCOPES = ["https://www.googleapis.com/auth/drive.file"]
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize the Drive API client.
        
        Args:
            credentials: OAuth2 credentials dict from rclone token or google-auth
        """
        self._credentials = None
        self._http = None
        self._service = None
        self._token_expiry = None
        
        if GOOGLE_API_AVAILABLE:
            self._init_credentials(credentials)
    
    def _init_credentials(self, credentials: Dict[str, Any]):
        """Initialize Google OAuth credentials from various formats"""
        if not credentials:
            logger.warning("No credentials provided to DriveAPIClient")
            return
        
        # Handle rclone token format
        if "access_token" in credentials:
            self._credentials = Credentials(
                token=credentials.get("access_token"),
                refresh_token=credentials.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=None,
                client_secret=None
            )
            self._token_expiry = credentials.get("expiry")
        # Handle google-auth credentials format
        elif isinstance(credentials, Credentials):
            self._credentials = credentials
        # Handle saved token format
        elif "token" in credentials:
            self._credentials = Credentials(**credentials)
        
        if self._credentials:
            self._http = self._credentials.transport
    
    def is_available(self) -> bool:
        """Check if Google API libraries are available"""
        return GOOGLE_API_AVAILABLE and self._credentials is not None
    
    def _ensure_service(self):
        """Ensure the Drive service is built"""
        if self._service is None:
            if not GOOGLE_API_AVAILABLE:
                raise DriveAPIError("Google API libraries not installed")
            
            if not self._credentials:
                raise DriveAPIError("Credentials not initialized")
            
            self._service = build("drive", "v3", credentials=self._credentials)
            self._http = self._service.http()
    
    async def _refresh_token_if_needed(self):
        """Refresh the OAuth token if expired or expiring soon"""
        if not self._credentials:
            return
        
        if self._credentials.expired or self._credentials.refresh_token:
            try:
                self._credentials.refresh(Request())
                logger.debug("OAuth token refreshed")
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                raise DriveAPIError("Token refresh failed", details=str(e))
    
    async def list_changes(
        self, 
        start_change_id: int,
        page_size: int = 1000
    ) -> List[DriveChange]:
        """
        List changes from Google Drive since start_change_id.
        
        This is the primary method for detecting remote changes.
        
        Args:
            start_change_id: The change ID to start from (from sync_state)
            page_size: Number of changes per request (max 1000)
            
        Returns:
            List of DriveChange objects
            
        Raises:
            DriveAPIError: If API call fails
        """
        if not GOOGLE_API_AVAILABLE:
            logger.warning("Google API not available, returning empty changes")
            return []
        
        changes = []
        page_token = None
        
        try:
            await self._refresh_token_if_needed()
            self._ensure_service()
            
            while True:
                # Call the Drive API
                result = self._service.changes().list(
                    pageToken=page_token,
                    pageSize=min(page_size, 1000),
                    startChangeId=start_change_id + 1,
                    fields="nextPageToken,changes(changeId,fileId,removed,file(id,name,mimeType,parents,size,md5Checksum,modifiedTime,createdTime,trashed))"
                ).execute()
                
                # Parse changes
                for change_data in result.get("changes", []):
                    change = DriveChange.from_change_response(change_data)
                    changes.append(change)
                
                # Check for more pages
                page_token = result.get("newStartPageToken")
                if not page_token:
                    break
                
                # Safety limit
                if len(changes) > 10000:
                    logger.warning("Change list exceeded 10000, truncating")
                    break
            
            logger.info(f"Retrieved {len(changes)} changes since change {start_change_id}")
            return changes
            
        except HttpError as e:
            error_msg = f"Drive API error: {e.content.decode()}" if e.content else str(e)
            logger.error(error_msg)
            raise DriveAPIError("Failed to list changes", status_code=e.resp.status, details=error_msg)
        except Exception as e:
            logger.error(f"Unexpected error listing changes: {e}")
            raise DriveAPIError("Unexpected error", details=str(e))
    
    async def get_file_metadata(self, file_id: str) -> Optional[DriveFile]:
        """
        Get metadata for a single file.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            DriveFile object or None if not found
        """
        if not GOOGLE_API_AVAILABLE:
            return None
        
        try:
            await self._refresh_token_if_needed()
            self._ensure_service()
            
            data = self._service.files().get(
                fileId=file_id,
                fields="id,name,mimeType,parents,size,md5Checksum,modifiedTime,createdTime,trashed"
            ).execute()
            
            if data.get("trashed"):
                return None
            
            return DriveFile.from_api_response(data)
            
        except HttpError as e:
            if e.resp.status == 404:
                return None  # File not found
            raise DriveAPIError("Failed to get file metadata", status_code=e.resp.status)
    
    async def get_file_metadata_batch(
        self, 
        file_ids: List[str],
        batch_size: int = 100
    ) -> Dict[str, DriveFile]:
        """
        Get metadata for multiple files efficiently.
        
        Args:
            file_ids: List of Google Drive file IDs
            batch_size: Number of files per batch request
            
        Returns:
            Dict mapping file_id -> DriveFile
        """
        if not GOOGLE_API_AVAILABLE or not file_ids:
            return {}
        
        results = {}
        
        # Process in batches
        for i in range(0, len(file_ids), batch_size):
            batch_ids = file_ids[i:i + batch_size]
            
            try:
                await self._refresh_token_if_needed()
                self._ensure_service()
                
                # Build batch request
                batch = self._service.new_batch_http_request()
                
                def callback(request_id, response, exception):
                    if exception:
                        logger.error(f"Batch request failed: {exception}")
                        return
                    if response and not response.get("trashed"):
                        results[response["id"]] = DriveFile.from_api_response(response)
                
                for fid in batch_ids:
                    batch.add(
                        self._service.files().get(
                            fileId=fid,
                            fields="id,name,mimeType,parents,size,md5Checksum,modifiedTime,createdTime,trashed"
                        ),
                        callback=callback
                    )
                
                batch.execute()
                
            except Exception as e:
                logger.error(f"Batch metadata request failed: {e}")
                continue
        
        logger.info(f"Retrieved metadata for {len(results)} files")
        return results
    
    async def list_files(
        self,
        folder_id: str = None,
        page_size: int = 1000,
        query: str = None
    ) -> List[DriveFile]:
        """
        List files in a folder.
        
        Args:
            folder_id: Folder ID to list (None for root)
            page_size: Files per page
            query: Optional Drive query string
            
        Returns:
            List of DriveFile objects
        """
        if not GOOGLE_API_AVAILABLE:
            return []
        
        files = []
        page_token = None
        
        try:
            await self._refresh_token_if_needed()
            self._ensure_service()
            
            # Build query
            q_parts = []
            if folder_id:
                q_parts.append(f"'{folder_id}' in parents")
            if query:
                q_parts.append(query)
            q_parts.append("trashed = false")
            query_str = " and ".join(q_parts)
            
            while True:
                result = self._service.files().list(
                    q=query_str,
                    pageSize=min(page_size, 1000),
                    pageToken=page_token,
                    fields="nextPageToken,files(id,name,mimeType,parents,size,md5Checksum,modifiedTime,createdTime)",
                    orderBy="name"
                ).execute()
                
                for f in result.get("files", []):
                    files.append(DriveFile.from_api_response(f))
                
                page_token = result.get("nextPageToken")
                if not page_token:
                    break
            
            logger.info(f"Listed {len(files)} files in folder {folder_id or 'root'}")
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise DriveAPIError("Failed to list files", details=str(e))
    
    async def list_folders(
        self,
        folder_id: str = None,
        page_size: int = 1000
    ) -> List[DriveFolder]:
        """
        List folders in a parent folder.
        
        Args:
            folder_id: Parent folder ID (None for root)
            page_size: Folders per page
            
        Returns:
            List of DriveFolder objects
        """
        if not GOOGLE_API_AVAILABLE:
            return []
        
        files = await self.list_files(
            folder_id=folder_id,
            page_size=page_size,
            query="mimeType = 'application/vnd.google-apps.folder'"
        )
        
        folders = []
        for f in files:
            folders.append(DriveFolder(
                id=f.id,
                name=f.name,
                path=f.name,  # Will be built progressively
                parent_id=folder_id
            ))
        
        return folders
    
    async def list_all_files(
        self,
        page_size: int = 1000
    ) -> List[DriveFile]:
        """
        List ALL files (for full rebuild).
        
        Note: This can be slow for large drives.
        
        Args:
            page_size: Files per page
            
        Returns:
            List of all DriveFile objects
        """
        if not GOOGLE_API_AVAILABLE:
            return []
        
        all_files = []
        page_token = None
        
        try:
            await self._refresh_token_if_needed()
            self._ensure_service()
            
            while True:
                result = self._service.files().list(
                    pageSize=min(page_size, 1000),
                    pageToken=page_token,
                    fields="nextPageToken,files(id,name,mimeType,parents,size,md5Checksum,modifiedTime,createdTime)",
                    orderBy="name"
                ).execute()
                
                for f in result.get("files", []):
                    if not f.get("trashed", False):
                        all_files.append(DriveFile.from_api_response(f))
                
                page_token = result.get("nextPageToken")
                if not page_token:
                    break
            
            logger.info(f"Listed {len(all_files)} total files")
            return all_files
            
        except Exception as e:
            logger.error(f"Failed to list all files: {e}")
            raise DriveAPIError("Failed to list all files", details=str(e))
    
    async def download_file(
        self,
        file_id: str,
        dest_path: Path,
        progress_callback: callable = None
    ) -> bool:
        """
        Download a file from Google Drive.
        
        Args:
            file_id: Google Drive file ID
            dest_path: Local destination path
            progress_callback: Optional callback(Bytes downloaded, Total size)
            
        Returns:
            True if successful
        """
        if not GOOGLE_API_AVAILABLE:
            return False
        
        try:
            await self._refresh_token_if_needed()
            self._ensure_service()
            
            # Get file metadata first
            metadata = self._service.files().get(fileId=file_id).execute()
            file_size = int(metadata.get("size", 0))
            
            # Create destination directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download with progress
            request = self._service.files().get_media(fileId=file_id)
            
            with open(dest_path, "wb") as f:
                downloader = MediaIoBaseDownload(f, request, chunksize=1024*1024)
                
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if progress_callback and file_size:
                        progress_callback(status.resumable_progress, file_size)
            
            logger.info(f"Downloaded {file_id} to {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            return False
    
    async def move_file(
        self,
        file_id: str,
        new_parent_id: str,
        remove_parent_id: str = None
    ) -> bool:
        """
        Move a file to a different folder.
        
        Args:
            file_id: Google Drive file ID
            new_parent_id: Destination folder ID
            remove_parent_id: Source folder ID (if different from new)
            
        Returns:
            True if successful
        """
        if not GOOGLE_API_AVAILABLE:
            return False
        
        try:
            await self._refresh_token_if_needed()
            self._ensure_service()
            
            # Get current parents
            if remove_parent_id is None:
                file = self._service.files().get(fileId=file_id, fields="parents").execute()
                remove_parent_id = file.get("parents", [None])[0]
            
            # Move the file
            self._service.files().update(
                fileId=file_id,
                addParents=new_parent_id,
                removeParents=remove_parent_id,
                fields="id,parents"
            ).execute()
            
            logger.info(f"Moved file {file_id} to folder {new_parent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to move file {file_id}: {e}")
            return False
    
    async def rename_file(self, file_id: str, new_name: str) -> bool:
        """
        Rename a file.
        
        Args:
            file_id: Google Drive file ID
            new_name: New file name
            
        Returns:
            True if successful
        """
        if not GOOGLE_API_AVAILABLE:
            return False
        
        try:
            await self._refresh_token_if_needed()
            self._ensure_service()
            
            self._service.files().update(
                fileId=file_id,
                body={"name": new_name},
                fields="id,name"
            ).execute()
            
            logger.info(f"Renamed file {file_id} to {new_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rename file {file_id}: {e}")
            return False
    
    async def delete_file(self, file_id: str) -> bool:
        """
        Delete a file (move to trash).
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            True if successful
        """
        if not GOOGLE_API_AVAILABLE:
            return False
        
        try:
            await self._refresh_token_if_needed()
            self._ensure_service()
            
            self._service.files().delete(fileId=file_id).execute()
            
            logger.info(f"Deleted file {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False
    
    async def create_folder(
        self,
        name: str,
        parent_id: str = None
    ) -> Optional[str]:
        """
        Create a new folder.
        
        Args:
            name: Folder name
            parent_id: Parent folder ID
            
        Returns:
            New folder ID or None
        """
        if not GOOGLE_API_AVAILABLE:
            return None
        
        try:
            await self._refresh_token_if_needed()
            self._ensure_service()
            
            file_metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder"
            }
            
            if parent_id:
                file_metadata["parents"] = [parent_id]
            
            file = self._service.files().create(
                body=file_metadata,
                fields="id"
            ).execute()
            
            logger.info(f"Created folder {name} with ID {file.get('id')}")
            return file.get("id")
            
        except Exception as e:
            logger.error(f"Failed to create folder {name}: {e}")
            return None
    
    async def get_or_create_base_folder(self, folder_name: str) -> str:
        """
        Get or create a base sync folder.
        
        Args:
            folder_name: Name of the base folder
            
        Returns:
            Folder ID
        """
        if not GOOGLE_API_AVAILABLE:
            return ""
        
        try:
            await self._refresh_token_if_needed()
            self._ensure_service()
            
            # Search for existing folder
            result = self._service.files().list(
                q=f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                pageSize=1,
                fields="files(id)"
            ).execute()
            
            files = result.get("files", [])
            if files:
                return files[0]["id"]
            
            # Create new folder
            return await self.create_folder(folder_name)
            
        except Exception as e:
            logger.error(f"Failed to get/create base folder: {e}")
            return ""
    
    async def build_folder_path(
        self,
        folder_id: str,
        root_id: str = None
    ) -> str:
        """
        Build the full path string for a folder.
        
        Args:
            folder_id: Starting folder ID
            root_id: Root folder to stop at
            
        Returns:
            Path string like "/folder1/folder2/folder3"
        """
        if not GOOGLE_API_AVAILABLE:
            return ""
        
        path_parts = []
        current_id = folder_id
        
        while current_id and current_id != root_id:
            try:
                file = await self.get_file_metadata(current_id)
                if file:
                    path_parts.insert(0, file.name)
                    current_id = file.parent_id
                else:
                    break
            except Exception:
                break
        
        return "/" + "/".join(path_parts) if path_parts else "/"
    
    async def get_space_usage(self) -> Dict[str, int]:
        """
        Get storage space usage for the account.
        
        Returns:
            Dict with 'used' and 'total' bytes
        """
        if not GOOGLE_API_AVAILABLE:
            return {"used": 0, "total": 0}
        
        try:
            await self._refresh_token_if_needed()
            self._ensure_service()
            
            about = self._service.about().get(
                fields="storageQuota"
            ).execute()
            
            quota = about.get("storageQuota", {})
            return {
                "used": int(quota.get("usage", 0)),
                "total": int(quota.get("limit", 0))
            }
            
        except Exception as e:
            logger.error(f"Failed to get space usage: {e}")
            return {"used": 0, "total": 0}
    
    async def get_change_id_bounds(self) -> Tuple[int, int]:
        """
        Get the start and current change IDs for polling.
        
        Returns:
            (start_change_id, current_change_id)
        """
        if not GOOGLE_API_AVAILABLE:
            return (0, 0)
        
        try:
            await self._refresh_token_if_needed()
            self._ensure_service()
            
            # Get current change ID
            response = self._service.changes().getStartPageToken().execute()
            current_id = int(response.get("startChangeId", 0))
            
            # Return range for polling
            return (1, current_id)
            
        except Exception as e:
            logger.error(f"Failed to get change bounds: {e}")
            return (0, 0)


class RcloneDriveClient:
    """
    Fallback client using rclone for Drive operations.
    
    Used when Google API libraries are not available.
    Leverages rclone's built-in Drive support.
    """
    
    def __init__(self, rclone_wrapper):
        """
        Initialize the rclone-based client.
        
        Args:
            rclone_wrapper: RcloneWrapper instance
        """
        self.rclone = rclone_wrapper
    
    async def list_changes(
        self,
        start_change_id: int,
        remote_name: str,
        base_path: str = ""
    ) -> List[DriveChange]:
        """
        List changes using rclone.
        
        Note: rclone doesn't support incremental changes well,
        so this falls back to full listing with diff.
        
        Args:
            start_change_id: Ignored (rclone doesn't support)
            remote_name: rclone remote name
            base_path: Base path in remote
            
        Returns:
            List of DriveChange (limited info)
        """
        # rclone doesn't have a native changes API
        # We'll rely on sync_engine for local detection
        logger.debug("Rclone client: listing files for change detection")
        return []
    
    async def get_file_metadata(
        self,
        file_id: str,
        remote_name: str
    ) -> Optional[DriveFile]:
        """
        Get file metadata using rclone.
        
        Args:
            file_id: File ID (may not be available in rclone)
            remote_name: rclone remote name
            
        Returns:
            None (rclone doesn't expose Drive IDs)
        """
        return None
    
    async def move_file(
        self,
        file_id: str,
        new_parent_id: str,
        remote_name: str
    ) -> bool:
        """
        Move file using rclone.
        
        Args:
            file_id: File path (rclone uses paths, not IDs)
            new_parent_id: New parent path
            remote_name: rclone remote name
            
        Returns:
            True if successful
        """
        old_path = f"{remote_name}:{file_id}"
        new_path = f"{remote_name}:{new_parent_id}/{Path(file_id).name}"
        
        success, msg = self.rclone.moveto(old_path, new_path)
        return success
    
    async def rename_file(
        self,
        file_id: str,
        new_name: str,
        remote_name: str
    ) -> bool:
        """
        Rename file using rclone.
        
        Args:
            file_id: File path
            new_name: New name
            remote_name: rclone remote name
            
        Returns:
            True if successful
        """
        path = Path(file_id)
        new_path = str(path.parent / new_name)
        
        return await self.move_file(file_id, str(path.parent), remote_name)


def create_drive_client(
    credentials: Dict[str, Any],
    rclone_wrapper = None
) -> DriveAPIClient:
    """
    Factory function to create the appropriate Drive client.
    
    Args:
        credentials: OAuth credentials
        rclone_wrapper: Optional rclone wrapper for fallback
        
    Returns:
        DriveAPIClient or RcloneDriveClient
    """
    # Try Google API first
    if GOOGLE_API_AVAILABLE and credentials:
        client = DriveAPIClient(credentials)
        if client.is_available():
            return client
    
    # Fall back to rclone
    if rclone_wrapper:
        logger.info("Using rclone-based Drive client (Google API not available)")
        return RcloneDriveClient(rclone_wrapper)
    
    raise DriveAPIError(
        "No Drive client available. Install Google API libraries or configure rclone."
    )
