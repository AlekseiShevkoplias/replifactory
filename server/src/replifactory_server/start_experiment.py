import requests
import json
import logging

logging.basicConfig(level=logging.DEBUG)

def start_experiment(experiment_id):
    url = f'http://localhost:5000/experiments/{experiment_id}/start'
    print(f"Starting experiment {experiment_id}")
    
    try:
        response = requests.post(url)
        print(f"Response status code: {response.status_code}")
        print(f"Response: {response.text}")
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    # Get the most recent experiment
    response = requests.get('http://localhost:5000/experiments')
    if response.status_code == 200:
        experiments = response.json()
        if experiments:
            latest_experiment = experiments[-1]
            start_experiment(latest_experiment['id'])
        else:
            print("No experiments found")
    else:
        print(f"Failed to get experiments: {response.text}") 