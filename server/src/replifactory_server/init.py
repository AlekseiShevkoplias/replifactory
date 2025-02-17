from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from flask_socketio import SocketIO
import logging
from pathlib import Path

from replifactory_server.routes import device_routes, experiment_routes, service_routes
from replifactory_server.database import db
from replifactory_server.database_models import MeasurementData
from replifactory_simulation.factory import SimulationFactory
from replifactory_simulation.growth_model import GrowthModelParameters
from replifactory_simulation.runner import SimulationRunner
from replifactory_core.base_device import BaseDeviceConfig
from replifactory_core.experiment import ExperimentConfig
from replifactory_server.monitor import ExperimentMonitor

logger = logging.getLogger(__name__)

def init_app(app, config=None):
    """Initialize the Flask application with all its components."""
    # Initialize SocketIO
    socketio = SocketIO(app, 
        cors_allowed_origins="*",
        logger=True,
        engineio_logger=True,
        async_mode='threading'
    )
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
    CORS(app, resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    db.init_app(app)
    Migrate(app, db)
    
    # Register blueprints
    app.register_blueprint(device_routes)
    app.register_blueprint(experiment_routes)
    app.register_blueprint(service_routes)
    
    return app

def init_device(app):
    """Initialize the device and simulation components."""
    with app.app_context():
        try:
            # Create database tables
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Initialize device based on mode
            logger.info(f"Current mode: {app.config['MODE']}")
            if app.config['MODE'] == 'simulation':
                logger.info("Initializing simulation mode")
                # Create monitor for event handling
                monitor = ExperimentMonitor()
                
                # Create factory with monitor
                factory = SimulationFactory(event_listener=monitor)
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