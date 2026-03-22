import boto3
import uuid

s3_client = boto3.client('s3', region_name='us-west-2')
BUCKET = 'seng533-lambda-performance-evaluation-assets-hamza'


def upload_file():
    file_name = f"exp1/{uuid.uuid4()}.txt"
    content = "x" * 1024  # 1 KB payload

    s3_client.put_object(
        Bucket=BUCKET,
        Key=file_name,
        Body=content
    )
    s3_client.delete_object(
        Bucket=BUCKET,
        Key=file_name
    )
