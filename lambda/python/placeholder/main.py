# Steps conducted
# 1- Create S3 Bucket to load/read files
# 2- create a function on lambda using python 3.14 and x86
import json
import boto3

s3_client = boto3.client('s3', region_name='ca-central-1')
def exp1_x86(event, context):
    file_name = event['file_name']
    content = event['content']

    if not file_name or not content:
        return {
            'statusCode': 400,
            'body': json.dumps('Missing file name or content')
        }
    try:
        s3_client.put_object(
            Bucket='seng533-project',
            Key=file_name,
            Body=content
        )
    
        return {
            'statusCode': 200,
            'body': json.dumps('File uploaded successfully')
        }
    
    except Exception as e:
        
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error while uploading file: {e}')
        }

