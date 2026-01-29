"""MinIO (S3-compatible) storage client for images and documents."""

import io
import logging
from datetime import timedelta
from typing import Optional, BinaryIO
from uuid import uuid4

import httpx
from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


class MinIOStorage:
    """
    MinIO storage client for managing trademark images and documents.

    Provides S3-compatible object storage operations.
    """

    def __init__(self):
        self._client: Optional[Minio] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> Minio:
        """Get or create MinIO client."""
        if self._client is None:
            self._client = Minio(
                endpoint=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_use_ssl,
            )
        return self._client

    async def __aenter__(self):
        """Async context manager entry."""
        self._http_client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._http_client:
            await self._http_client.aclose()

    def ensure_bucket(self, bucket_name: Optional[str] = None) -> bool:
        """
        Ensure bucket exists, create if it doesn't.

        Args:
            bucket_name: Bucket name, uses default from settings if not provided

        Returns:
            True if bucket exists or was created
        """
        bucket = bucket_name or settings.minio_bucket_name

        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
                logger.info(f"Created bucket: {bucket}")

                # Set bucket policy for public read access to images
                policy = f'''{{
                    "Version": "2012-10-17",
                    "Statement": [
                        {{
                            "Effect": "Allow",
                            "Principal": {{"AWS": "*"}},
                            "Action": ["s3:GetObject"],
                            "Resource": ["arn:aws:s3:::{bucket}/images/*"]
                        }}
                    ]
                }}'''

                self.client.set_bucket_policy(bucket, policy)
                logger.info(f"Set public read policy for images in {bucket}")

            return True

        except S3Error as e:
            logger.error(f"Error ensuring bucket {bucket}: {e}")
            return False

    def upload_file(
        self,
        file_data: BinaryIO,
        object_name: str,
        content_type: str = "application/octet-stream",
        bucket_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Upload a file to MinIO.

        Args:
            file_data: File-like object to upload
            object_name: Name/path for the object in storage
            content_type: MIME type of the file
            bucket_name: Bucket name

        Returns:
            Object name if successful, None otherwise
        """
        bucket = bucket_name or settings.minio_bucket_name

        try:
            self.ensure_bucket(bucket)

            # Get file size
            file_data.seek(0, 2)
            file_size = file_data.tell()
            file_data.seek(0)

            self.client.put_object(
                bucket_name=bucket,
                object_name=object_name,
                data=file_data,
                length=file_size,
                content_type=content_type,
            )

            logger.info(f"Uploaded {object_name} to {bucket}")
            return object_name

        except S3Error as e:
            logger.error(f"Error uploading {object_name}: {e}")
            return None

    def upload_bytes(
        self,
        data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
        bucket_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Upload bytes to MinIO.

        Args:
            data: Bytes to upload
            object_name: Name/path for the object
            content_type: MIME type
            bucket_name: Bucket name

        Returns:
            Object name if successful
        """
        return self.upload_file(
            io.BytesIO(data),
            object_name,
            content_type,
            bucket_name
        )

    async def download_and_upload_image(
        self,
        image_url: str,
        trademark_id: str,
        source: str = "unknown",
    ) -> Optional[str]:
        """
        Download image from URL and upload to MinIO.

        Args:
            image_url: URL to download image from
            trademark_id: Trademark ID for naming
            source: Source identifier (fips, wipo)

        Returns:
            Object name if successful
        """
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=30.0)

        try:
            logger.info(f"Downloading image from {image_url}")

            response = await self._http_client.get(
                image_url,
                follow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )

            if response.status_code != 200:
                logger.warning(f"Failed to download image: HTTP {response.status_code}")
                return None

            # Determine content type and extension
            content_type = response.headers.get('content-type', 'image/jpeg')
            extension = self._get_extension(content_type, image_url)

            # Generate unique filename
            filename = f"{trademark_id}_{uuid4().hex[:8]}{extension}"
            object_name = f"images/{source}/{filename}"

            # Upload to MinIO
            result = self.upload_bytes(
                response.content,
                object_name,
                content_type
            )

            if result:
                logger.info(f"Uploaded image as {object_name}")

            return result

        except Exception as e:
            logger.error(f"Error downloading/uploading image: {e}")
            return None

    def _get_extension(self, content_type: str, url: str) -> str:
        """Determine file extension from content type or URL."""
        # Try content type
        type_map = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'image/svg+xml': '.svg',
            'image/bmp': '.bmp',
            'image/tiff': '.tiff',
        }

        for mime, ext in type_map.items():
            if mime in content_type.lower():
                return ext

        # Try URL extension
        for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
            if ext in url.lower():
                return ext if ext != '.jpeg' else '.jpg'

        return '.jpg'  # Default

    def get_url(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
        expires: timedelta = timedelta(hours=1),
    ) -> Optional[str]:
        """
        Get presigned URL for an object.

        Args:
            object_name: Object name/path
            bucket_name: Bucket name
            expires: URL expiration time

        Returns:
            Presigned URL or None
        """
        bucket = bucket_name or settings.minio_bucket_name

        try:
            url = self.client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=expires
            )
            return url

        except S3Error as e:
            logger.error(f"Error getting URL for {object_name}: {e}")
            return None

    def get_public_url(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
    ) -> str:
        """
        Get public URL for an object (requires public bucket policy).

        Args:
            object_name: Object name/path
            bucket_name: Bucket name

        Returns:
            Public URL
        """
        bucket = bucket_name or settings.minio_bucket_name
        protocol = "https" if settings.minio_use_ssl else "http"

        return f"{protocol}://{settings.minio_endpoint}/{bucket}/{object_name}"

    def delete_file(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
    ) -> bool:
        """
        Delete a file from MinIO.

        Args:
            object_name: Object name/path
            bucket_name: Bucket name

        Returns:
            True if deleted successfully
        """
        bucket = bucket_name or settings.minio_bucket_name

        try:
            self.client.remove_object(bucket, object_name)
            logger.info(f"Deleted {object_name} from {bucket}")
            return True

        except S3Error as e:
            logger.error(f"Error deleting {object_name}: {e}")
            return False

    def list_files(
        self,
        prefix: str = "",
        bucket_name: Optional[str] = None,
    ) -> list[str]:
        """
        List files in bucket with optional prefix.

        Args:
            prefix: Filter by prefix (folder path)
            bucket_name: Bucket name

        Returns:
            List of object names
        """
        bucket = bucket_name or settings.minio_bucket_name
        files = []

        try:
            objects = self.client.list_objects(bucket, prefix=prefix, recursive=True)
            for obj in objects:
                files.append(obj.object_name)

        except S3Error as e:
            logger.error(f"Error listing files: {e}")

        return files

    def file_exists(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
    ) -> bool:
        """
        Check if file exists in bucket.

        Args:
            object_name: Object name/path
            bucket_name: Bucket name

        Returns:
            True if file exists
        """
        bucket = bucket_name or settings.minio_bucket_name

        try:
            self.client.stat_object(bucket, object_name)
            return True
        except S3Error:
            return False
