import json
import boto3
import base64

client = boto3.client('lambda')

payload ={
    'file_name': 'test-text-file',
}
response = client.invoke(
    FunctionName='lambda-function-name',
    Payload=json.dumps(payload)
)

print(response['Payload'].read())