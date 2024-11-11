'''
    This code exists so I can test things at a very basic
    level on my machine and then run things on the machine
    in the TSRB. 
'''

import requests
import json

api_url = "http://localhost:11434/api/generate"

headers = {
    "Content-Type": "application/json"
}

data = {
    "model": "llama3.2",
    "prompt": "What color is the sky?",
    "stream": False
}

# Generate ollama response
response = requests.post(api_url, headers=headers, data=json.dumps(data))

if response.status_code == 200:
    response_text = response.text
    data = json.loads(response_text)
    print(data["response"])
    eval_count = data["eval_count"]
    eval_duration = data["eval_duration"]
    tokens_per_second = eval_count / (eval_duration * pow(10, 9))
    print("Tokens Per Second: " + tokens_per_second)
else:
    print("Unable to get a response")
