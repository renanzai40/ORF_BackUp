"""AWS S3 Resource Client

Provides S3 operations for downloading, uploading, and managing blob storage.
Uses boto3 Session for client creation with proper error handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from orf.cloud.cloud_resource_manager import CloudClient
from orf.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("cloud.s3")


def __getattr__(name: str) -> Any:
    if name == "boto3":
        import boto3
        return boto3
    if name == "ClientError":
        from botocore.exceptions import ClientError
        return ClientError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class S3ResourceClient(CloudClient):
    """S3 resource operations client.

    Provides methods for common S3 operations including download, upload,
    existence checks, and listing objects under a prefix.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        """Initialize S3 client.

        Args:
            bucket: S3 bucket name
            prefix: Optional prefix path for all operations
            region_name: Optional AWS region (uses boto3 defaults if None)
            endpoint_url: Optional endpoint URL for S3-compatible services
        """
        self.bucket = bucket
        self.prefix = prefix.rstrip("/")

        session_kwargs = {}
        if region_name:
            session_kwargs["region_name"] = region_name

        import boto3
        self.session = boto3.Session(**session_kwargs)

        client_kwargs = {"service_name": "s3"}
        if region_name:
            client_kwargs["region_name"] = region_name
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url

        self._client = self.session.client(**client_kwargs)

    def _full_key(self, key: str) -> str:
        """Construct full S3 key from relative key and configured prefix.

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
        """Download an S3 object to a local path.

        Args:
            key: S3 object key
            dest: Local destination path

        Returns:
            True if download succeeded, False on error
        """
        dest = Path(dest)
        full_key = self._full_key(key)

        from botocore.exceptions import ClientError
        try:
            logger.debug(f"Downloading s3://{self.bucket}/{full_key} to {dest}")
            self._client.download_file(self.bucket, full_key, str(dest))
            logger.info(f"Downloaded s3://{self.bucket}/{full_key} to {dest}")
            return True
        except ClientError as e:
            logger.error(f"Failed to download {full_key}: {e}")
            return False

    def upload(self, source: Path | str, key: str) -> bool:
        """Upload a local file to S3.

        Args:
            source: Local file path to upload
            key: S3 destination key

        Returns:
            True if upload succeeded, False on error
        """
        source = Path(source)
        full_key = self._full_key(key)

        if not source.exists():
            logger.error(f"Source file does not exist: {source}")
            return False

        from botocore.exceptions import ClientError
        try:
            logger.debug(f"Uploading {source} to s3://{self.bucket}/{full_key}")
            self._client.upload_file(str(source), self.bucket, full_key)
            logger.info(f"Uploaded {source} to s3://{self.bucket}/{full_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload {source}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if an S3 object exists.

        Args:
            key: S3 object key

        Returns:
            True if object exists, False otherwise
        """
        full_key = self._full_key(key)

        from botocore.exceptions import ClientError
        try:
            self._client.head_object(Bucket=self.bucket, Key=full_key)
            logger.debug(f"Object exists: s3://{self.bucket}/{full_key}")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.debug(f"Object does not exist: s3://{self.bucket}/{full_key}")
                return False
            logger.error(f"Error checking existence of {full_key}: {e}")
            return False

    def list_resources(self, prefix: str = "") -> list[str]:
        """List S3 objects under a prefix.

        Args:
            prefix: Prefix to list under (appended to client's prefix)

        Returns:
            List of object keys under the prefix
        """
        search_prefix = self._full_key(prefix) if prefix else self.prefix

        from botocore.exceptions import ClientError
        try:
            logger.debug(f"Listing objects with prefix: {search_prefix}")
            response = self._client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=search_prefix,
            )
            contents = response.get("Contents", [])
            keys = [obj["Key"] for obj in contents]
            logger.debug(f"Found {len(keys)} objects under prefix {search_prefix}")
            return keys
        except ClientError as e:
            logger.error(f"Failed to list objects under {search_prefix}: {e}")
            return []