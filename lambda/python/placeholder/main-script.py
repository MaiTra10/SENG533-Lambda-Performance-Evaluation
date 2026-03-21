import json
import boto3
import base64

client = boto3.client('lambda')
with open('test.txt','r') as f:
    content = f.read()

payload ={
    'file_name': 'test-text-file-2',
    'content': content
}
response = client.invoke(
    FunctionName='input-output-script-seng-py',
    Payload=json.dumps(payload)
)

print(response['Payload'].read())