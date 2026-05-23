"""ORF Cloud Storage Clients

S3 and other cloud storage resource operations.
"""

from __future__ import annotations

from typing import Any

from orf.cloud.cloud_resource_manager import CloudClient, CloudResourceManager

# Lazy imports to avoid requiring azure/boto3 unless using these clients
# Users should import specific clients directly if needed


def __getattr__(name: str) -> Any:
    if name == "S3ResourceClient":
        from orf.cloud.s3_client import S3ResourceClient

        return S3ResourceClient
    elif name == "AzureBlobResourceClient":
        from orf.cloud.azure_blob_client import AzureBlobResourceClient

        return AzureBlobResourceClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CloudClient",
    "CloudResourceManager",
    "S3ResourceClient",
    "AzureBlobResourceClient",
]