const url = 'https://test.intel4coro.de/built-repo';

// Define the JSON data to send
const jsonData = {"providerSpec":"gh/yxzhan/giskard-examples/mujoco_actions_devel","path":"notebooks/playground.ipynb?robot=pr2_mujoco","pathType":"lab"};

// Define the options for the fetch request
const options = {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(jsonData)
};

// Send the POST request
fetch(url, options)
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        console.log('Response:', data);
    })
    .catch(error => {
        console.error('Error:', error);
    });