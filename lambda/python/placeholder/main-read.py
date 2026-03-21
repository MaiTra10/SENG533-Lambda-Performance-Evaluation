import json
import boto3

s3_client = boto3.client('s3', region_name='ca-central-1')
def lambda_handler(event, context):
    file_name = event['file_name']

    try:
        response = s3_client.get_object(
            Bucket='Bucket-name',
            Key=file_name,
        )
        file_content = response['Body'].read()
        return {
            'statusCode': 200,
            'body': file_content
        }
    except Exception as e:
    
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error while fetching the file: {e}')
        }
