import json
import boto3

client = boto3.client('lambda')
with open('test.txt','r') as f:
    content = f.read()

payload ={
    'file_name': 'test-text-file-2',
    'content': content
}
response = client.invoke(
    FunctionName='lambda-function-name',
    Payload=json.dumps(payload)
)

print(response['Payload'].read())
