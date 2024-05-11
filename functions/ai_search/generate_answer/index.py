import boto3
import json
import os


client = boto3.client('bedrock-runtime', region_name=os.environ["AWS_REGION"])

# Set the model ID for Claude 3 Haiku
model_id = "anthropic.claude-3-haiku-20240307-v1:0"

def handler(event, context):
    question = event["user_question"]
    sources = event["output_sources"]

    # Define the prompt and parameters
    prompt = f"""Your job is to anwser the user's question using information provided in the sources section below.

    {sources}
    
    Now please answer the user's quesiton: 

    {question}

    """

    params = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "system": "please always answer in the same language of the user's question",
        "messages": [
            {
                "role": "user", 
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    }

    # Invoke the model
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(params)
    )

    # Process the response
    response_body = json.loads(response['body'].read())
    for output in response_body['content']:
        return output['text']