"""Azure Blob Storage Resource Client

Provides Azure Blob operations for downloading, uploading, and managing blob storage.
Uses azure-storage-blob BlobServiceClient for operations with proper error handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from orf.cloud.cloud_resource_manager import CloudClient
from orf.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("cloud.azure_blob")


def __getattr__(name: str) -> Any:
    if name == "BlobServiceClient":
        from azure.storage.blob import BlobServiceClient
        return BlobServiceClient
    if name == "ResourceNotFoundError":
        from azure.core.exceptions import ResourceNotFoundError
        return ResourceNotFoundError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class AzureBlobResourceClient(CloudClient):
    """Azure Blob resource operations client.

    Provides methods for common Azure Blob operations including download, upload,
    existence checks, and listing blobs under a prefix.
    Mirrors the interface of S3ResourceClient for cross-cloud compatibility.
    """

    def __init__(
        self,
        connection_string: str,
        container: str,
        prefix: str = "",
    ):
        """Initialize Azure Blob client.

        Args:
            connection_string: Azure Blob storage connection string
            container: Container name
            prefix: Optional prefix path for all operations
        """
        self.container = container
        self.prefix = prefix.rstrip("/")
        import azure.storage.blob
        self._blob_service_client = azure.storage.blob.BlobServiceClient.from_connection_string(
            connection_string
        )

    def _full_key(self, key: str) -> str:
        """Construct full blob path from relative key and configured prefix.

        Args:
            key: Relative key or full key

        Returns:
            Full key with prefix
        """
        key = key.lstrip("/")
        if self.prefix:
            return f"{self.prefix}/{key}"
        return key

    def download(self, key: str, dest: Path | str) -> bool:
        """Download an Azure blob to a local path.

        Args:
            key: Blob path
            dest: Local destination path

        Returns:
            True if download succeeded, False on error
        """
        dest = Path(dest)
        full_key = self._full_key(key)

        from azure.core.exceptions import ResourceNotFoundError
        try:
            blob_client = self._blob_service_client.get_blob_client(
                container=self.container, blob=full_key
            )
            logger.debug(f"Downloading {full_key} from {self.container} to {dest}")
            with open(dest, "wb") as f:
                download_stream = blob_client.download_blob()
                f.write(download_stream.readall())
            logger.info(f"Downloaded {full_key} from {self.container} to {dest}")
            return True
        except ResourceNotFoundError as e:
            logger.error(f"Blob not found: {full_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to download {full_key}: {e}")
            return False

    def upload(self, source: Path | str, key: str) -> bool:
        """Upload a local file to Azure Blob.

        Args:
            source: Local file path to upload
            key: Blob destination path

        Returns:
            True if upload succeeded, False on error
        """
        source = Path(source)
        full_key = self._full_key(key)

        if not source.exists():
            logger.error(f"Source file does not exist: {source}")
            return False

        try:
            blob_client = self._blob_service_client.get_blob_client(
                container=self.container, blob=full_key
            )
            logger.debug(f"Uploading {source} to {full_key} in {self.container}")
            with open(source, "rb") as f:
                blob_client.upload_blob(f, overwrite=True)
            logger.info(f"Uploaded {source} to {full_key} in {self.container}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload {source}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if a blob exists.

        Args:
            key: Blob path

        Returns:
            True if blob exists, False otherwise
        """
        full_key = self._full_key(key)

        from azure.core.exceptions import ResourceNotFoundError
        try:
            blob_client = self._blob_service_client.get_blob_client(
                container=self.container, blob=full_key
            )
            blob_client.get_blob_properties()
            logger.debug(f"Blob exists: {full_key}")
            return True
        except ResourceNotFoundError:
            logger.debug(f"Blob does not exist: {full_key}")
            return False
        except Exception as e:
            logger.error(f"Error checking existence of {full_key}: {e}")
            return False

    def list_resources(self, prefix: str = "") -> list[str]:
        """List blobs under a path prefix.

        Args:
            prefix: Prefix to list under (appended to client's prefix)

        Returns:
            List of blob paths under the prefix
        """
        search_prefix = self._full_key(prefix) if prefix else self.prefix

        try:
            container_client = self._blob_service_client.get_container_client(
                self.container
            )
            logger.debug(f"Listing blobs with prefix: {search_prefix}")
            blob_list = container_client.list_blobs(name_starts_with=search_prefix)
            keys = [blob.name for blob in blob_list]
            logger.debug(f"Found {len(keys)} blobs under prefix {search_prefix}")
            return keys
        except Exception as e:
            logger.error(f"Failed to list blobs under {search_prefix}: {e}")
            return []