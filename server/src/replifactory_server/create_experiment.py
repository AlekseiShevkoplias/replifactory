import requests
import json
import logging

logging.basicConfig(level=logging.DEBUG)

def create_experiment():
    experiment_data = {
        "name": "Test Experiment",
        "parameters": {
            # Experiment duration settings
            "max_duration_hours": 24,
            "measurement_interval_mins": 1,
            
            # Culture configuration
            "culture_config": {
                "od_threshold": 0.3,
                "growth_rate_threshold": 0.15,
                "min_growth_rate": -0.1,
                "dilution_factor": 1.6,
                "max_drug_concentration": 100.0
            },
            
            # Device configuration
            "device_config": {
                "n_vials": 2  # Only include valid parameters
            }
        }
    }
    
    url = 'http://localhost:5000/experiments'
    print(f"Sending POST request to: {url}")
    print(f"Request data: {json.dumps(experiment_data, indent=2)}")
    
    try:
        response = requests.post(
            url,
            json=experiment_data,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response text: {response.text}")
        
        if response.status_code == 201:
            print("Experiment created successfully!")
            print(json.dumps(response.json(), indent=2))
            
            # Start the experiment
            experiment_id = response.json()['id']
            start_url = f'http://localhost:5000/experiments/{experiment_id}/start'
            print(f"\nStarting experiment {experiment_id}...")
            start_response = requests.post(start_url)
            print(f"Start response: {start_response.text}")
        else:
            print(f"Error creating experiment: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    create_experiment() 