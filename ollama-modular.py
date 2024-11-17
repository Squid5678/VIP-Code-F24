import requests
import json
import yaml
import os

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

    data = {
        "model": config['model']['name'],
        "prompt": prompt,
        "stream": config['model']['parameters']['stream']
    }

    # Make API request
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
    else:
        print("Unable to get a response")

if __name__ == "__main__":
    main()