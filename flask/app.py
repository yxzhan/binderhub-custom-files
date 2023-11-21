from flask import Flask, jsonify, request
from urllib.parse import unquote, urlparse
from time import time
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=['http://10.0.0.100', 'https://binder.intel4coro.de'])

# Initialize an empty list
built_repo_list = []

# Todos: save list to exteranl storage
def save_list_to_file():
    print(built_repo_list)
    
def get_repo_list():
    return jsonify(sorted(built_repo_list, key=lambda x:x["timestamp"], reverse=True))

def update_built_list(data):
    providerSpec = data['providerSpec']
    repo_base_url = ''
    repo_url = ''
    repo_author = ''
    repo_name = ''
    repo_ref = ''
    components = providerSpec.strip('/').split('/')
    if components[0] == 'gh':
        repo_base_url = 'https://github.com'
        repo_author = components[1]
        repo_name = components[2].replace('.git', '')
        repo_ref = components[3]
        repo_url =  f"{repo_base_url}/{components[1]}/{repo_name}/tree/{components[3]}"
    if components[0] == 'git':
        repo_ref = components[2]
        repo_url_obj = urlparse(unquote(components[1]))
        repo_author = repo_url_obj.path.strip('/').split('/')[0]
        repo_name = repo_url_obj.path.strip('/').split('/')[1].replace('.git', '')
        repo_url =  f"{repo_url_obj.scheme}://{repo_url_obj.netloc}/{repo_author}/{repo_name}/tree/{repo_ref}"

    new_repo = {
        'id': data['providerSpec'],
        'repo_url': repo_url,
        'repo_author': repo_author,
        'repo_name': repo_name,
        'repo_ref': repo_ref,
        'timestamp': time(),
        # 'binder': f"/{providerSpec}?{data['pathType']}url={data['path']}"
        'binder': f"/{providerSpec}"
    }
    
    previous_built = find_dict_by_id( data['providerSpec'], built_repo_list)
    if previous_built is None:
        built_repo_list.append(new_repo)
    else:
        previous_built.update(new_repo)
    return new_repo


def find_dict_by_id(id_to_find, d_list):
    for item in d_list:
        if item.get('id') == id_to_find:
            return item
    return None  # Return None if id is not found

# Endpoint to insert a string into the list
@app.route('/', methods=['POST'])
def post_request():
    data = request.json
    if 'providerSpec' not in data:
        return jsonify({'error': 'Please provide repo info in the request'}), 400
    try:
        new_repo = update_built_list(data)
        return jsonify({'message': f"Repo {new_repo['repo_url']} added successfully"}), 200
    except Exception as e:
        print(e)
        return jsonify({'error': 'Internal Server Error!'}), 500

# Endpoint to get the values of the list
@app.route('/', methods=['GET'])
def get_request():
    return get_repo_list()

if __name__ == '__main__':
    flask_port = os.getenv('FLASK_PORT')
    debug = os.getenv('FLASK_DEBUG')
    print(type(debug))
    app.run(debug=debug,host='0.0.0.0', port=flask_port if flask_port is not None else 9091)