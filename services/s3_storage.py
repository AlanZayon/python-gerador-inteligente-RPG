import boto3
import os
from uuid import uuid4

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ["AWS_REGION"],
)

BUCKET = os.environ["S3_BUCKET_NAME"]


def upload_pdf_to_s3(local_path: str, filename: str) -> dict:
    """
    Faz upload do PDF para o S3 e retorna key + URL pré-assinada
    """
    s3_key = f"campaign-inputs/{uuid4()}_{filename}"

    s3.upload_file(
        Filename=local_path,
        Bucket=BUCKET,
        Key=s3_key,
        ExtraArgs={"ContentType": "application/pdf"}
    )

    presigned_url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": BUCKET,
            "Key": s3_key
        },
        ExpiresIn=3600  # 1 hora
    )

    return {
        "s3_key": s3_key,
        "file_url": presigned_url
    }
    

def upload_content_to_s3(content: str, filename: str) -> dict:
    s3_key = f"campaigns/{filename}"
    s3.put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=content.encode('utf-8'),
        ContentType='text/markdown'
    )
    presigned_url = s3.generate_presigned_url(
        ClientMethod='get_object',
        Params={'Bucket': BUCKET, 'Key': s3_key},
        ExpiresIn=3600
    )
    return {'s3_key': s3_key, 'file_url': presigned_url}

