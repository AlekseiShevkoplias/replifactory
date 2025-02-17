from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import json
import logging

from replifactory_core.experiment import Experiment, ExperimentConfig
from replifactory_core.base_device import BaseDeviceConfig
from replifactory_server.database import db
from replifactory_server.database_models import ExperimentModel, MeasurementData
from replifactory_core.culture import CultureConfig

# Create blueprints
device_routes = Blueprint('device_routes', __name__)
experiment_routes = Blueprint('experiment_routes', __name__)
service_routes = Blueprint('service_routes', __name__)

logger = logging.getLogger(__name__)

# Add service routes
@service_routes.route('/service/status', methods=['GET'])
def get_service_status():
    return jsonify({
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'mode': current_app.config.get('MODE', 'unknown')
    })


@device_routes.route('/device/status', methods=['GET'])
def get_device_status():
    if not hasattr(current_app, 'device'):
        return jsonify({'error': 'Device not initialized'}), 500
    return jsonify({'status': 'ready'})

@device_routes.route('/device/measurements', methods=['GET'])
def get_device_measurements():
    if not hasattr(current_app, 'device'):
        return jsonify({'error': 'Device not initialized'}), 500
        
    vial = request.args.get('vial', type=int)
    if not vial or not 1 <= vial <= current_app.device.config.n_vials:
        return jsonify({'error': 'Invalid vial number'}), 400
        
    try:
        measurements = current_app.device.measure_vial(vial)
        return jsonify({
            'od': measurements.od,
            'temperature': measurements.temperature,
            'rpm': measurements.rpm
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@device_routes.route('/device/pump', methods=['POST'])
def activate_pump():
    try:
        data = request.get_json()
        pump_id = data.get('pump')
        volume = data.get('volume')

        if not pump_id or not volume:
            return jsonify({'error': 'Missing pump id or volume'}), 400

        if not hasattr(current_app, 'device'):
            return jsonify({'error': 'Device not initialized'}), 500

        # Activate the pump
        current_app.device.activate_pump(pump_id, volume)
        
        return jsonify({'message': f'Pump {pump_id} activated with volume {volume}mL'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@device_routes.route('/device/valve', methods=['POST'])
def set_valve_state():
    try:
        data = request.get_json()
        valve_id = data.get('valve')
        state = data.get('state')

        if valve_id is None or state is None:
            return jsonify({'error': 'Missing valve id or state'}), 400

        if not hasattr(current_app, 'device'):
            return jsonify({'error': 'Device not initialized'}), 500

        # Set the valve state
        current_app.device.set_valve_state(valve_id, state)
        
        return jsonify({'message': f'Valve {valve_id} set to {"open" if state else "closed"}'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Experiment routes
experiment_routes = Blueprint('experiment_routes', __name__)

@experiment_routes.route('/experiments', methods=['GET'])
def get_experiments():
    experiments = ExperimentModel.query.all()
    return jsonify([exp.to_dict() for exp in experiments])

@experiment_routes.route('/experiments', methods=['POST'])
def create_experiment():
    try:
        data = request.get_json()
        logger.debug(f"Received experiment data: {data}")
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Create new experiment record
        experiment = ExperimentModel(
            name=data.get('name', f'Experiment_{datetime.now().strftime("%Y%m%d_%H%M%S")}'),
            parameters=data.get('parameters', {})
        )
        experiment.status = 'created'  # Set status after creation
        
        # Save to database
        db.session.add(experiment)
        db.session.commit()
        
        logger.info(f"Created experiment: {experiment.id}")
        
        return jsonify({
            'message': 'Experiment created successfully',
            'id': experiment.id,
            'name': experiment.name,
            'status': experiment.status
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating experiment: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@experiment_routes.route('/experiments/<int:id>', methods=['GET'])
def get_experiment(id):
    experiment = ExperimentModel.query.get_or_404(id)
    return jsonify(experiment.to_dict())

@experiment_routes.route('/experiments/current/status', methods=['PUT'])
def update_experiment_status():
    status = request.json['status']
    
    if not hasattr(current_app, 'experiment'):
        return jsonify({'error': 'No experiment selected'}), 404
        
    if status == 'running':
        current_app.experiment.start()
    elif status == 'stopped':
        current_app.experiment.stop()
    elif status == 'paused':
        current_app.experiment.pause()
        
    return jsonify({'message': f'Experiment {status}'})

@experiment_routes.route('/plot/<int:vial>', methods=['GET'])
def get_culture_plot(vial):
    if not hasattr(current_app, 'experiment'):
        return jsonify({'error': 'No experiment selected'}), 404
        
    measurements = MeasurementData.query.filter_by(
        experiment_id=current_app.experiment.model.id,
        vial=vial
    ).order_by(MeasurementData.timestamp).all()
    
    # Create plot data
    data = {
        'times': [m.timestamp.isoformat() for m in measurements],
        'ods': [m.od for m in measurements],
        'drug_concentrations': [m.drug_concentration for m in measurements],
        'growth_rates': [m.growth_rate for m in measurements]
    }
    
    return jsonify(data)

@experiment_routes.route('/experiments/<int:id>/start', methods=['POST'])
def start_experiment(id):
    try:
        exp_model = ExperimentModel.query.get_or_404(id)
        
        # Get parameters from database
        parameters = json.loads(exp_model.parameters) if isinstance(exp_model.parameters, str) else exp_model.parameters
        
        # Create culture config from parameters
        culture_config = CultureConfig(
            od_threshold=parameters['culture_config'].get('od_threshold', 0.3),
            growth_rate_threshold=parameters['culture_config'].get('growth_rate_threshold', 0.15),
            min_growth_rate=parameters['culture_config'].get('min_growth_rate', -0.1),
            dilution_factor=parameters['culture_config'].get('dilution_factor', 1.6),
            max_drug_concentration=parameters['culture_config'].get('max_drug_concentration', 100.0)
        )
        
        # Create experiment config
        config = ExperimentConfig(
            max_duration_hours=parameters.get('max_duration_hours', 24),
            measurement_interval_mins=parameters.get('measurement_interval_mins', 1),
            culture_config=culture_config,
            device_config=BaseDeviceConfig(**parameters.get('device_config', {}))
        )
        
        # Initialize experiment
        if not hasattr(current_app, 'device'):
            current_app.logger.error("Device not initialized")
            return jsonify({'error': 'Device not initialized'}), 500
            
        # Create experiment
        current_app.experiment = Experiment(
            device=current_app.device,
            config=config,
            protocol=current_app.simulation_runner.protocol if hasattr(current_app, 'simulation_runner') else None
        )
        current_app.experiment.model = exp_model  # Set the experiment model
        
        # Start the experiment
        if hasattr(current_app, 'simulation_runner'):
            current_app.logger.info("Starting experiment in simulation mode")
            current_app.simulation_runner.experiment = current_app.experiment
            current_app.simulation_runner.experiment.model = exp_model  # Set the model on the simulation runner's experiment
            current_app.simulation_runner.start()
        else:
            current_app.logger.info("Starting experiment in hardware mode")
            current_app.experiment.start()
        
        # Update experiment status in database
        exp_model.status = 'running'
        db.session.commit()
        
        return jsonify({
            'message': 'Experiment started successfully',
            'experiment': {
                'id': exp_model.id,
                'name': exp_model.name,
                'status': exp_model.status
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error starting experiment: {str(e)}")
        return jsonify({'error': str(e)}), 500

@experiment_routes.route('/experiments/active', methods=['GET'])
def get_active_experiment():
    """Get currently running experiment."""
    try:
        current_app.logger.info("Fetching active experiment...")
        
        # Get the most recent running experiment
        experiment = ExperimentModel.query\
            .filter_by(status='running')\
            .order_by(ExperimentModel.created_at.desc())\
            .first()
            
        response_data = {'experiment': experiment.to_dict() if experiment else None}
        response = current_app.make_response(response_data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        
        if experiment:
            current_app.logger.info(f"Found active experiment: ID={experiment.id}, Name={experiment.name}")
        else:
            current_app.logger.info("No active experiments found")
            
        return response
            
    except Exception as e:
        current_app.logger.error(f"Error getting active experiment: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# Add to_dict method to ExperimentModel
def to_dict(self):
    return {
        'id': self.id,
        'name': self.name,
        'status': self.status,
        'parameters': json.loads(self.parameters) if isinstance(self.parameters, str) else self.parameters,
        'created_at': self.created_at.isoformat() if self.created_at else None
    }

ExperimentModel.to_dict = to_dict