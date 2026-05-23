"""Unified Cloud Resource Manager

Provides a unified interface for cloud storage operations across
different providers (S3, Azure Blob) by delegating to provider-specific clients.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal, Optional

from orf.logging import get_logger

logger = get_logger("cloud.manager")


class CloudClient(ABC):
    """Abstract base class for cloud resource clients.

    Defines the interface that all cloud storage clients must implement
    for cross-cloud compatibility.
    """

    @abstractmethod
    def download(self, key: str, dest: Path | str) -> bool:
        """Download a resource from cloud storage.

        Args:
            key: Remote resource key/path
            dest: Local destination path

        Returns:
            True if download succeeded, False on error
        """
        ...

    @abstractmethod
    def upload(self, source: Path | str, key: str) -> bool:
        """Upload a resource to cloud storage.

        Args:
            source: Local source file path
            key: Remote destination key/path

        Returns:
            True if upload succeeded, False on error
        """
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a resource exists in cloud storage.

        Args:
            key: Remote resource key/path

        Returns:
            True if resource exists, False otherwise
        """
        ...

    @abstractmethod
    def list_resources(self, prefix: str = "") -> list[str]:
        """List resources under a path prefix.

        Args:
            prefix: Prefix to list under

        Returns:
            List of resource paths/keys under the prefix
        """
        ...


class CloudResourceManager:
    """Unified interface for cloud resource operations.

    Factory that creates provider-specific clients and delegates
    all operations to the underlying client for cross-cloud compatibility.

    Supported providers:
        - "s3": Amazon S3 (uses S3ResourceClient)
        - "azure": Azure Blob Storage (uses AzureBlobResourceClient)

    Usage:
        # S3
        manager = CloudResourceManager(provider="s3", config={
            "bucket": "my-bucket",
            "prefix": "data/",
            "region_name": "us-east-1",
        })
        manager.download_resource("remote/file.txt", "/local/path")

        # Azure Blob
        manager = CloudResourceManager(provider="azure", config={
            "connection_string": "...",
            "container": "my-container",
            "prefix": "data/",
        })
        manager.upload_resource("/local/file.txt", "remote/file.txt")
    """

    _PROVIDERS: dict[str, type[CloudClient]] = {}
    _initialized = False

    @classmethod
    def register_provider(cls, provider: str, client_class: type[CloudClient]) -> None:
        """Register a cloud provider client class.

        Args:
            provider: Provider name (e.g., "s3", "azure")
            client_class: CloudClient subclass for the provider
        """
        cls._PROVIDERS[provider.lower()] = client_class

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Lazy initialization of default providers."""
        if cls._initialized:
            return
        cls._initialized = True
        try:
            from orf.cloud.s3_client import S3ResourceClient
            cls.register_provider("s3", S3ResourceClient)
        except ImportError:
            pass
        try:
            from orf.cloud.azure_blob_client import AzureBlobResourceClient
            cls.register_provider("azure", AzureBlobResourceClient)
        except ImportError:
            pass

    def __init__(
        self,
        provider: Literal["s3", "azure"],
        config: Optional[dict[str, Any]] = None,
    ):
        """Initialize CloudResourceManager.

        Args:
            provider: Cloud provider name ("s3" or "azure")
            config: Provider-specific configuration dict

        Raises:
            ValueError: If provider is not supported or config is invalid
        """
        self.provider = provider.lower()
        self.config = config or {}

        self._ensure_initialized()

        if self.provider not in self._PROVIDERS:
            available = ", ".join(self._PROVIDERS.keys()) or "none"
            raise ValueError(
                f"Unsupported provider: {provider}. Available: {available}"
            )

        self._client: CloudClient = self._create_client()

    def _create_client(self) -> CloudClient:
        """Create the provider-specific client instance.

        Returns:
            Instantiated cloud client

        Raises:
            ValueError: If required config keys are missing
        """
        client_class: Any = self._PROVIDERS[self.provider]

        if self.provider == "s3":
            return client_class(  # type: ignore[no-any-return]
                bucket=self.config.get("bucket", ""),
                prefix=self.config.get("prefix", ""),
                region_name=self.config.get("region_name"),
                endpoint_url=self.config.get("endpoint_url"),
            )
        elif self.provider == "azure":
            return client_class(  # type: ignore[no-any-return]
                connection_string=self.config.get("connection_string", ""),
                container=self.config.get("container", ""),
                prefix=self.config.get("prefix", ""),
            )
        else:
            # Should not reach here due to __init__ validation
            raise ValueError(f"Unsupported provider: {self.provider}")

    def download_resource(self, remote: str, local: Path | str) -> bool:
        """Download a resource from cloud storage.

        Args:
            remote: Remote resource path/key
            local: Local destination path

        Returns:
            True if download succeeded, False on error
        """
        logger.debug(
            f"Downloading {remote} to {local} using {self.provider} client"
        )
        return self._client.download(remote, local)

    def upload_resource(self, local: Path | str, remote: str) -> bool:
        """Upload a resource to cloud storage.

        Args:
            local: Local source file path
            remote: Remote destination path/key

        Returns:
            True if upload succeeded, False on error
        """
        logger.debug(
            f"Uploading {local} to {remote} using {self.provider} client"
        )
        return self._client.upload(local, remote)

    def resource_exists(self, remote: str) -> bool:
        """Check if a resource exists in cloud storage.

        Args:
            remote: Remote resource path/key

        Returns:
            True if resource exists, False otherwise
        """
        logger.debug(
            f"Checking existence of {remote} using {self.provider} client"
        )
        return self._client.exists(remote)

    def list_resources(self, prefix: str = "") -> list[str]:
        """List resources under a path prefix.

        Args:
            prefix: Prefix to list under

        Returns:
            List of resource paths/keys under the prefix
        """
        logger.debug(
            f"Listing resources with prefix '{prefix}' using {self.provider} client"
        )
        return self._client.list_resources(prefix)