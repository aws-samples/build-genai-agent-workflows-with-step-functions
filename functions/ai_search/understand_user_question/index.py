import json
import boto3
import os

# create bedrock client
client = boto3.client('bedrock-runtime', region_name=os.environ["AWS_REGION"])

# Set the model ID for Claude 3 Haiku
model_id = "anthropic.claude-3-haiku-20240307-v1:0"

def handler(event, context):
    print(event)
    question = event["user_question"]

    # Define the prompt and parameters
    system_prompt = """Your job is to create high quality search engine keywords based on the user's question. Please always respond in valid JSON. 

    Here are a few response examples: 

    {"keywords": ["top news today", "current news headlines", "today's top stories"]}
    {"keywords": ["xz hack", "amazon linux", "security vulnerabilities"]}

    """

    prompt = f"""Please answer this question with at most 3 search engine keywords.

    Question: {question}
        
    """

    params = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 250,
        "system": system_prompt,
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
        payload = json.loads(output['text'])
        print(payload)

        return payload['keywords']
