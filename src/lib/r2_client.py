import os
import logging
from pathlib import Path
import boto3
from botocore.config import Config
from lib.config import settings

logger = logging.getLogger(__name__)

class R2Client:
    def __init__(self):
        self.is_mocked = (
            settings.R2_ACCOUNT_ID == "placeholder_account_id" or
            settings.R2_ACCESS_KEY_ID == "placeholder_access_key"
        )
        if self.is_mocked:
            logger.warning("Cloudflare R2 is configured with placeholders. Falling back to local filesystem storage mock!")
            # Define local storage paths
            self.local_storage_dir = Path("storage")
            self.local_storage_dir.mkdir(exist_ok=True)
            (self.local_storage_dir / "uploads").mkdir(exist_ok=True)
            (self.local_storage_dir / "previews").mkdir(exist_ok=True)
            (self.local_storage_dir / "results").mkdir(exist_ok=True)
            self.s3_client = None
        else:
            endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
                region_name="auto"
            )
            self.bucket_name = settings.R2_BUCKET_NAME

    def upload_file(self, file_content: bytes, key: str, content_type: str = "binary/octet-stream") -> str:
        """Uploads file content to Cloudflare R2 or local mockup folder and returns public/mockup URL."""
        if self.is_mocked:
            # Write to local file mock
            local_path = self.local_storage_dir / key
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(file_content)
            # URL relative to local server serving static files
            # E.g., http://localhost:8000/static/uploads/filename.mp4
            return f"{settings.R2_PUBLIC_URL}/{key}"
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_content,
                ContentType=content_type
            )
            # Return R2 URL
            if settings.R2_PUBLIC_URL:
                return f"{settings.R2_PUBLIC_URL.rstrip('/')}/{key}"
            else:
                return f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{settings.R2_BUCKET_NAME}/{key}"
        except Exception as e:
            logger.error(f"Failed to upload file to R2: {str(e)}")
            raise e

    def download_file(self, key: str) -> bytes:
        """Downloads file content from R2 or local mockup folder and returns bytes."""
        if self.is_mocked:
            local_path = self.local_storage_dir / key
            return local_path.read_bytes()

        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Failed to download file from R2: {str(e)}")
            raise e

    def delete_file(self, key: str):
        """Deletes file from R2 or local mockup folder."""
        if self.is_mocked:
            local_path = self.local_storage_dir / key
            if local_path.exists():
                local_path.unlink()
                logger.info(f"Mock storage: Deleted local file {key}")
            return

        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"R2 Storage: Deleted file {key}")
        except Exception as e:
            logger.error(f"Failed to delete file from R2: {str(e)}")
            raise e

    def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """Generates a presigned URL for secure download."""
        if self.is_mocked:
            return f"{settings.R2_PUBLIC_URL}/{key}"
            
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            raise e

r2_client = R2Client()
