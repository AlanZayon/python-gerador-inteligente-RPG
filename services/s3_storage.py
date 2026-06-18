import os
from uuid import uuid4

_s3_client = None
PRESIGNED_URL_TTL = int(os.getenv("PRESIGNED_URL_TTL", str(24 * 3600)))


def _bucket_name() -> str:
    bucket = os.getenv("S3_BUCKET_NAME", "")
    if not bucket:
        raise RuntimeError("S3_BUCKET_NAME is not configured")
    return bucket


def s3_configured() -> bool:
    return bool(
        os.getenv("AWS_ACCESS_KEY_ID")
        and os.getenv("AWS_SECRET_ACCESS_KEY")
        and os.getenv("S3_BUCKET_NAME")
    )


def _get_s3_client():
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    if not s3_configured():
        raise RuntimeError(
            "AWS S3 is not configured. Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and S3_BUCKET_NAME."
        )
    import boto3

    _s3_client = boto3.client(
        "s3",
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )
    return _s3_client


def upload_pdf_to_s3(local_path: str, filename: str) -> dict:
    """Upload PDF to S3 and return key + presigned URL."""
    s3 = _get_s3_client()
    bucket = _bucket_name()
    s3_key = f"campaign-inputs/{uuid4()}_{filename}"

    s3.upload_file(
        Filename=local_path,
        Bucket=bucket,
        Key=s3_key,
        ExtraArgs={"ContentType": "application/pdf"},
    )

    presigned_url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=PRESIGNED_URL_TTL,
    )

    return {"s3_key": s3_key, "file_url": presigned_url}


def generate_presigned_url(s3_key: str) -> str:
    s3 = _get_s3_client()
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": _bucket_name(), "Key": s3_key},
        ExpiresIn=PRESIGNED_URL_TTL,
    )


def fetch_s3_text(s3_key: str) -> str | None:
    try:
        s3 = _get_s3_client()
        obj = s3.get_object(Bucket=_bucket_name(), Key=s3_key)
        return obj["Body"].read().decode("utf-8")
    except Exception:
        return None


def delete_s3_object(s3_key: str) -> None:
    try:
        s3 = _get_s3_client()
        s3.delete_object(Bucket=_bucket_name(), Key=s3_key)
    except Exception:
        pass


def upload_content_to_s3(content: str, filename: str) -> dict:
    s3 = _get_s3_client()
    bucket = _bucket_name()
    s3_key = f"campaigns/{filename}"
    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=content.encode("utf-8"),
        ContentType="text/markdown",
    )
    presigned_url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=PRESIGNED_URL_TTL,
    )
    return {"s3_key": s3_key, "file_url": presigned_url}
