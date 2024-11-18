import requests
import json
import yaml
import os
import tiktoken  # for token counting

def load_config(path='ollama_test_config.yaml'): 
    with open(path, 'r') as file:
        return yaml.safe_load(file)

def load_prompt(prompt_file_path):
    try:
        with open(prompt_file_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Prompt file not found: {prompt_file_path}")
    except Exception as e:
        raise Exception(f"Error reading prompt file: {str(e)}")

def count_tokens(text, model_name):
    try:
        encoding_map = {
            "llama2": "cl100k_base",
            "llama3": "cl100k_base",
        }
        
        base_model = ''.join([i for i in model_name if not i.isdigit() and i != '.'])
        
        encoding_name = encoding_map.get(base_model, "cl100k_base")
        
        encoding = tiktoken.get_encoding(encoding_name)
        
        token_count = len(encoding.encode(text))
        return token_count
    except Exception as e:
        print(f"Error counting tokens: {str(e)}")
        return None

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    config_path = os.path.join(current_dir, 'ollama_test_config.yaml')
    config = load_config(config_path)

    api_url = config['api']['url']
    headers = config['api']['headers']
    print(headers)

    prompt_file_path = os.path.join(current_dir, config['test']['prompt_file'])
    
    try:
        prompt = load_prompt(prompt_file_path)
    except Exception as e:
        print(f"Error loading prompt: {str(e)}")
        return

    if config['metrics']['show_token_count']:
        token_count = count_tokens(prompt, config['model']['name'])
        if token_count:
            print(f"Prompt Token Count: {token_count}")

    data = {
        "model": config['model']['name'],
        "prompt": prompt,
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
            tokens_per_second = eval_count / eval_duration * pow(10, 9)
            print("Tokens Per Second:", tokens_per_second)
            
        if config['metrics']['show_token_count']:
            response_token_count = count_tokens(data["response"], config['model']['name'])
            if response_token_count:
                print(f"Response Token Count: {response_token_count}")
                print(f"Total Token Count: {token_count + response_token_count}")
    else:
        print("Unable to get a response")

if __name__ == "__main__":
    main()