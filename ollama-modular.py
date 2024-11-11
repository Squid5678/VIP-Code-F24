import requests
import json
import yaml
import os

def load_config(path='ollama_test_config.yaml'):
    with open (path, 'r') as file:
        return yaml.safe_load(file)
    
def main():
    config = load_config()

    api_url = config['api']['url']
    headers = config['api']['headers']

    data = {
        "model": config['model']['name'],
        "prompt": config['test']['prompt'],
        "stream": config['model']['parameters']['stream']
    }

    response = requests.post(api_url, headers=headers, data=json.dumps(data))


    if response.status_code == 200:
        response_text = response.text
        data = json.loads(response_text)
        print(data["response"])
        
        if config['metrics']['show_tokens_per_second']:
            eval_count = data["eval_count"]
            eval_duration = data["eval_duration"]
            tokens_per_second = eval_count / (eval_duration * pow(10, 9))
            print("Tokens Per Second:", tokens_per_second)
    else:
        print("Unable to get a response")


if __name__ == "__main__":
    main()

