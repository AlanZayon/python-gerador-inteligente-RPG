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

def upload_pdf_to_s3(local_path, filename):
    s3_key = f"campaign-inputs/{uuid4()}_{filename}"

    s3.upload_file(
        local_path,
        BUCKET,
        s3_key,
        ExtraArgs={"ContentType": "application/pdf"}
    )

    return f"https://{BUCKET}.s3.amazonaws.com/{s3_key}"
