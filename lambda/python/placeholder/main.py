import boto3

s3 = boto3.client("s3")

BUCKET = "seng533-lambda-performance-evaluation-assets"
KEY = "test-object.txt"

def handler(event, context):
    for _ in range(3):
        response = s3.get_object(Bucket=BUCKET, Key=KEY)
        response["Body"].read()

    return {
        "statusCode": 200
    }