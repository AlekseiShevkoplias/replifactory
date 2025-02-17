from datetime import datetime
from replifactory_core.protocols import MorbidostatProtocol, MorbidostatConfig
from dataclasses import asdict
import logging
from threading import Thread
from typing import Optional
import time
from replifactory_core.base_device import BaseDevice
from replifactory_core.experiment import ExperimentConfig, Experiment
from replifactory_simulation.simulation_factory import SimulationFactory
from replifactory_simulation.growth_model import GrowthModelParameters
from replifactory_simulation.logging import SimulationLogger, MeasurementLog


from .simulation_factory import SimulationFactory
from .growth_model import GrowthModelParameters
from .logging import SimulationLogger
import time
from threading import Thread, Event
from typing import Optional
import logging
from flask_sqlalchemy import SQLAlchemy
from replifactory_server.database_models import db, MeasurementData
from dataclasses import asdict

db = SQLAlchemy()
logger = logging.getLogger(__name__)

class SimulationRunner:
    """Runs simulated evolution experiments."""
    
    def __init__(
        self,
        config: ExperimentConfig = ExperimentConfig(),
        model_params: Optional[GrowthModelParameters] = None,
        time_acceleration: float = 100.0,
        device: Optional[BaseDevice] = None,
        app=None,
        db=None,  # Add database parameter
        measurement_model=None  # Add measurement model parameter
    ):
        self._log = logging.getLogger("SimulationRunner")
        self.time_acceleration = time_acceleration
        self.config = config
        self.model_params = model_params or GrowthModelParameters()  # Store model_params
        self._running = False
        self._thread: Optional[Thread] = None
        self.app = app
        self.db = db  # Store database reference
        self.measurement_model = measurement_model  # Store measurement model reference
        
        # Create device if not provided
        if device is None:
            factory = SimulationFactory()
            device = factory.create_device(config.device_config, self.model_params)
        self.device = device
        
        # Initialize protocol
        self.protocol = MorbidostatProtocol(MorbidostatConfig())
        
        # Initialize experiment
        self.experiment = Experiment(
            device=self.device,
            config=self.config,
            protocol=self.protocol
        )
        
        # Initialize data logging
        self.data_logger = SimulationLogger(
            output_dir="data/experiments",
            experiment_id=self.experiment.name
        )
        self.data_logger.log_config(asdict(config))
        
    def start(self):
        if self._thread is not None and self._thread.is_alive():
            self._log.warning("Simulation already running")
            return
            
        self._running = True
        
        # Log initial state
        self.data_logger.log_config({
            'experiment': self.config.__dict__,
            'growth_model': self.model_params.__dict__,
            'time_acceleration': self.time_acceleration
        })
        
        # Start experiment
        self._log.info("Starting experiment...")
        self.experiment.start()
        
        # Take initial measurements
        self._log.info("Taking initial measurements...")
        try:
            self._update_simulation()
        except Exception as e:
            self._log.error(f"Error taking initial measurements: {str(e)}")
            self.experiment.stop()
            return
            
        # Start simulation thread
        self._thread = Thread(
            target=self._run_simulation,
            name="SimulationThread",
            daemon=True
        )
        self._thread.start()
        self._log.info("Simulation started")
        
    def stop(self):
        self._log.info("Stopping simulation...")
        self._running = False
        
        if self._thread and self._thread.is_alive():
            # Wait with timeout
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                self._log.warning("Simulation thread did not stop cleanly")
        
        self._thread = None
        self.experiment.stop()
        self._log.info("Simulation stopped")
        
    def _run_simulation(self):
        try:
            update_interval = self.config.measurement_interval_mins * 60  # seconds
            update_interval /= self.time_acceleration
            
            self._last_update = time.time()
            self._log.info(f"Update interval: {update_interval:.2f} seconds")
            
            while self._running and self.experiment._status == "running":
                current_time = time.time()
                elapsed = current_time - self._last_update
                
                if elapsed >= update_interval:
                    self._log.debug(f"Running update at {current_time}")
                    try:
                        self._update_simulation()
                        self._last_update = current_time
                    except Exception as e:
                        self._log.error(f"Update error: {e}")
                        if not isinstance(e, (ValueError, RuntimeError)):
                            raise
                
                # Prevent CPU spinning while checking more frequently
                time.sleep(min(0.1, update_interval / 10))
                
        except Exception as e:
            self._log.error(f"Simulation error: {e}")
            self.data_logger.log_event('error', {'message': str(e)})
        finally:
            if self.experiment._status != "stopped":
                self.experiment.stop()
                
    def _update_simulation(self):
        """Update simulation state and record measurements."""
        # Update growth models
        od_sensor = self.device._od_sensor
        for vial in range(1, self.config.device_config.n_vials + 1):
            model = od_sensor._growth_models[vial]
            timestep = self.config.measurement_interval_mins / self.time_acceleration
            model.update(timestep_mins=timestep)
        
        # Update experiment
        self.experiment.update()
        
        # Log status
        status = self.experiment.status
        for vial, data in status['cultures'].items():
            if data is None:
                self._log.warning(f"No data for vial {vial}")
                continue
                
            # Extract values with safe defaults
            od = data.get('od', 0.0)
            drug_conc = data.get('drug_concentration', 0.0)
            growth_rate = data.get('growth_rate', 0.0)
            temp = data.get('temperature', 37.0)
            
            # Log status
            self._log.info(
                f"Vial {vial}: OD={od:.3f}, Drug={drug_conc:.1f}, "
                f"Growth Rate={growth_rate:.3f}/hr"
            )
            
            # Save to database if app context is available
            if self.app and self.db and self.measurement_model and hasattr(self.experiment, 'model'):
                try:
                    with self.app.app_context():
                        measurement = self.measurement_model(
                            experiment_id=self.experiment.model.id,
                            vial=vial,
                            timestamp=datetime.now(),
                            od=od,
                            temperature=temp,
                            drug_concentration=drug_conc,
                            growth_rate=growth_rate
                        )
                        self.db.session.add(measurement)
                        self.db.session.commit()
                        self._log.debug(f"Saved measurement for vial {vial} to database")
                except Exception as e:
                    self._log.error(f"Failed to save measurement to database: {str(e)}")
            
            # Record measurement in data logger
            self.data_logger.log_measurement(
                vial=vial,
                od=od,
                temperature=temp,
                drug_concentration=drug_conc,
                growth_rate=growth_rate,
                action=data.get('last_action')
            )
        
        if status.get('error'):
            self._log.error(f"Experiment error: {status['error']}")
            self.data_logger.log_event('error', {'message': status['error']})
