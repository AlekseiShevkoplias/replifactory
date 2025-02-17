from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
import logging
import os
from pathlib import Path
from waitress import serve
from flask_socketio import SocketIO

from replifactory_server.routes import device_routes, experiment_routes, service_routes
from replifactory_server.database import db
from replifactory_server.database_models import MeasurementData
from replifactory_simulation.factory import SimulationFactory
from replifactory_simulation.growth_model import GrowthModelParameters
from replifactory_simulation.runner import SimulationRunner
from replifactory_core.base_device import BaseDeviceConfig
from replifactory_core.experiment import ExperimentConfig
import sys

logger = logging.getLogger(__name__)


def create_app(config=None):
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Create Flask app
    app = Flask(__name__)
    
    # Initialize SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*")
    app.config['socketio'] = socketio
    
    # Ensure instance folder exists
    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)
    
    # Set database path
    db_path = instance_path / 'replifactory.db'
    
    # Load default configuration
    default_config = {
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'MODE': 'simulation',  # Default to simulation mode
        'DATABASE_PATH': db_path,
        'TIME_ACCELERATION': 100.0
    }
    
    # Apply default config
    app.config.from_mapping(default_config)
    
    # Override with provided config if any
    if config:
        app.config.update(config)
    
    logger.info(f"Database path: {db_path}")
    logger.info(f"Running in {app.config['MODE']} mode")
    
    # Initialize extensions
    CORS(app)
    db.init_app(app)
    Migrate(app, db)
    
    # Register blueprints
    app.register_blueprint(device_routes)
    app.register_blueprint(experiment_routes)
    app.register_blueprint(service_routes)
    
    # Initialize device and simulation
    with app.app_context():
        try:
            # Create database tables
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Initialize device based on mode
            logger.info(f"Current mode: {app.config['MODE']}")
            if app.config['MODE'] == 'simulation':
                logger.info("Initializing simulation mode")
                factory = SimulationFactory()
                device_config = BaseDeviceConfig()
                model_params = GrowthModelParameters()
                
                # Create device
                app.device = factory.create_device(device_config, model_params)
                logger.info("Device created successfully")
                
                # Create simulation runner
                app.simulation_runner = SimulationRunner(
                    device=app.device,
                    config=ExperimentConfig(),
                    model_params=model_params,
                    time_acceleration=app.config.get('TIME_ACCELERATION', 100.0),
                    app=app,
                    db=db,
                    measurement_model=MeasurementData
                )
                logger.info(f"Simulation initialized with {app.config.get('TIME_ACCELERATION', 100.0)}x time acceleration")
                logger.info(f"Device initialized: {hasattr(app, 'device')}")
                logger.info(f"Simulation runner initialized: {hasattr(app, 'simulation_runner')}")
            else:
                logger.info("Initializing hardware mode")
                # Initialize hardware device here
                pass
                
        except Exception as e:
            logger.error(f"Error during initialization: {str(e)}")
            logger.error(f"Current app config: {app.config}")
            raise
    
    return app

def run_server(host='0.0.0.0', port=5000, mode='simulation', config=None):
    if config is None:
        config = {}
    config['MODE'] = mode
    
    app = create_app(config)
    logger.info(f"Starting server in {mode} mode on {host}:{port}")
    logger.info(f"Time acceleration factor: {app.config.get('TIME_ACCELERATION', 100.0)}x")
    
    socketio = app.config['socketio']
    socketio.run(app, host=host, port=port)

def main():
    development = len(sys.argv) > 1 and sys.argv[1] == 'develop'
    
    config = {
        'MODE': 'simulation',  # Always use simulation mode
        'TIME_ACCELERATION': 100.0
    }
    
    if development:
        print("Running in development mode")
        app = create_app(config)
        app.run(debug=True, host="0.0.0.0", port=5000)
    else:
        print("Running in production mode")
        run_server(host="0.0.0.0", port=5000, mode='simulation', config=config)

if __name__ == '__main__':
    main()