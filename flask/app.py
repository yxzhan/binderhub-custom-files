from flask import Flask, jsonify, request
from urllib.parse import unquote, urlparse
import threading
import time
import os
import json
from flask_cors import CORS
from ollama import Client
import requests

app = Flask(__name__)
CORS(app, origins=['*'])

# init ollama client
# curl http://ollama:11434/api/generate -d '{"model": "llama3.2:3b", "keep_alive": -1}'
LLM_MODEL = 'llama3.2:3b'
ollama_client = Client(host='ollama:11434')

def load_json_to_list(filename):
    with open(filename, 'r') as f:
        data = json.load(f)
    return data

# Initialize an empty list
built_repo_list = load_json_to_list('./built-repo.json')
built_images_file = './built-images.json'

# Todos: save list to exteranl storage
def save_list_to_file():
    global built_repo_list
    current_time = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"./backup/built-repo_{current_time}.json"
    with open(filename, 'w') as f:
        json.dump(built_repo_list, f, indent=2)
    print(f"List saved to {filename}")
    built_repo_list = get_repo_list()[:50]
    
# Function to run the save_data_to_json function periodically
def scheduler_func():
    while True:
        save_list_to_file()
        fetch_all_docker_images()
        time.sleep(24 * 60 * 60)  # Sleep for 24* 60 minutes

# Start the scheduler function in a separate thread
scheduler_thread = threading.Thread(target=scheduler_func)
scheduler_thread.daemon = True  # Daemonize the thread so it will be terminated when the main thread exits
scheduler_thread.start()

def get_repo_list():
    return sorted(built_repo_list, key=lambda x:x["timestamp"], reverse=True)

def fetch_all_docker_images():
    username = 'intel4coro'
    result = {}
    try:
        # Get list of repositories (Docker images)
        repos = list_docker_images(username)
        for repo in repos:
            tags = list_image_tags(username, repo)
            result[repo] = tags
    except Exception as e:
        return []
    with open(built_images_file, 'w') as f:
        json.dump(result, f, indent=2)
    return result

def list_docker_images(username):
    """
    List all repositories (Docker images) of a public Docker Hub account.
    """
    repositories = []
    page = 1
    while True:
        url = f"https://hub.docker.com/v2/repositories/{username}/?page={page}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            repos = data.get('results', [])
            repositories.extend([repo['name'] for repo in repos])
            
            # If there are more pages, continue, else break
            if data.get('next') is not None:
                page += 1
            else:
                break
        else:
            raise Exception(f"Failed to retrieve repositories: {response.status_code} {response.text}")
    
    return repositories

def list_image_tags(username, repository):
    """
    List all tags of a Docker repository.
    """
    tags = []
    page = 1
    while True:
        url = f"https://hub.docker.com/v2/repositories/{username}/{repository}/tags/?page={page}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            tags.extend([tag['name'] for tag in data.get('results', [])])
            
            # If there are more pages, continue, else break
            if data.get('next') is not None:
                page += 1
            else:
                break
        else:
            raise Exception(f"Failed to retrieve tags for {repository}: {response.status_code} {response.text}")
    
    return tags

def update_built_list(data):
    providerSpec = data['providerSpec']
    repo_base_url = ''
    repo_url = ''
    repo_author = ''
    repo_name = ''
    repo_ref = ''
    repo_launch_path = data['path']
    repo_launch_type = data['pathType']
    components = providerSpec.strip('/').split('/')
    repo_prefix = components[0]
    if repo_prefix == 'gh':
        repo_base_url = 'https://github.com'
        repo_author = components[1]
        repo_name = components[2].replace('.git', '')
        repo_ref = components[3]
        repo_url =  f"{repo_base_url}/{components[1]}/{repo_name}/tree/{components[3]}"
    if repo_prefix == 'git':
        repo_ref = components[2]
        repo_url_obj = urlparse(unquote(components[1]))
        repo_author = repo_url_obj.path.strip('/').split('/')[0]
        repo_name = repo_url_obj.path.strip('/').split('/')[1].replace('.git', '')
        repo_url =  f"{repo_url_obj.scheme}://{repo_url_obj.netloc}/{repo_author}/{repo_name}/tree/{repo_ref}"
    repo_id =  f"{repo_prefix}/{repo_author}/{repo_name}/{repo_ref}"
    new_repo = {
        'id': repo_id,
        'repo_prefix': repo_prefix,
        'repo_url': repo_url,
        'repo_author': repo_author,
        'repo_name': repo_name,
        'repo_ref': repo_ref,
        'timestamp': time.time(),
        'binder': f"/{providerSpec}" + (f"?{repo_launch_type}path={repo_launch_path}" if repo_launch_type else '')
    }
    previous_built = find_dict_by_id(repo_id, built_repo_list)
    if previous_built is None:
        built_repo_list.append(new_repo)
    else:
        previous_built.update(new_repo)
    return new_repo

def find_dict_by_id(id_to_find, d_list):
    for item in d_list:
        if item['id'] == id_to_find:
            return item
    return None  # Return None if id is not found

def llm_explain_error(error_msg):
    response = ollama_client.chat(model=LLM_MODEL, messages=[
    {
        'role': 'tool',
        'content': f'''
        Interpret the following error messages for non-technical users, the error message is from a public BinderHub services.
        If it is about insufficient server resources, prompt the user to try again later.
        Keeping the response less than three sentences.
        Error message: 
        "{error_msg}"
        ''',
    }])
    return response['message']['content']

    
@app.route('/error', methods=['POST'])
def explain_error():
    data = request.json
    return jsonify({'data': llm_explain_error(data['data'])})

# Endpoint to insert a string into the list
@app.route('/built-repo', methods=['POST'])
def post_request():
    data = request.json
    if 'providerSpec' not in data:
        return jsonify({'error': 'Please provide repo info in the request'}), 400
    try:
        new_repo = update_built_list(data)
        return jsonify({'message': f"Repo {new_repo['repo_url']} added successfully"}), 200
    except Exception as e:
        return jsonify({'error': 'Internal Server Error!'}), 500

# Endpoint to get the values of the list
@app.route('/built-repo', methods=['GET'])
def get_request():
    return jsonify(get_repo_list())
    
@app.route('/image', methods=['GET'])
def get_built_image():
    try:
        if not os.path.exists(built_images_file):
            fetch_all_docker_images()
        with open(built_images_file, 'r') as file:
            data = json.load(file)
            return data, 200
    except Exception as e:
        return jsonify({'error': e}), 500

if __name__ == '__main__':
    flask_port = os.getenv('FLASK_PORT')
    debug = os.getenv('FLASK_DEBUG')
    app.run(debug=True,host='0.0.0.0', port=flask_port if flask_port is not None else 9091)