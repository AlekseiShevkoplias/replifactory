import time
from threading import Thread, Event
from typing import Optional

from replifactory_core.experiment import Experiment, ExperimentConfig
from replifactory_core.protocols import MorbidostatProtocol, MorbidostatConfig
from replifactory_core.base_device import BaseDeviceConfig

from .factory import SimulationFactory
from .growth_model import GrowthModelParameters
from .logging import SimulationLogger

import time
from threading import Thread, Event
from typing import Optional
import logging

class SimulationRunner:
    def __init__(
        self,
        config: Optional[ExperimentConfig] = None,
        model_params: Optional[GrowthModelParameters] = None,
        time_acceleration: float = 1.0
    ):
        self.config = config or ExperimentConfig()
        self.model_params = model_params or GrowthModelParameters()
        self.time_acceleration = max(0.1, time_acceleration)  # Prevent zero/negative
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("SimulationRunner")
        
        # Create simulated device with validated config
        factory = SimulationFactory()
        device_config = BaseDeviceConfig(
            n_vials=min(7, max(1, self.config.device_config.n_vials))
        )
        
        # Initialize experiment
        self.device = factory.create_device(device_config, self.model_params)
        self.experiment = Experiment(
            device=self.device,
            config=self.config,
            name=f"simulation_{int(time.time())}"
        )
        
        # Initialize data logger
        self.data_logger = SimulationLogger(output_dir="simulation_logs")
        
        # Control flags
        self._stop_event = Event()
        self._simulation_thread: Optional[Thread] = None
        self._last_update = 0
        
    def start(self):
        """Start simulation in background thread with proper error handling."""
        if self._simulation_thread is not None and self._simulation_thread.is_alive():
            self.logger.warning("Simulation already running")
            return
            
        self._stop_event.clear()
        self._simulation_thread = Thread(
            target=self._run_simulation,
            name="SimulationThread",
            daemon=True  # Ensure thread doesn't block program exit
        )
        self._simulation_thread.start()
        
        self.data_logger.log_config({
            'experiment': self.config.__dict__,
            'growth_model': self.model_params.__dict__,
            'time_acceleration': self.time_acceleration
        })
        
        self.logger.info("Simulation started")
        
    def stop(self):
        """Safely stop simulation."""
        if self._simulation_thread is None:
            return
            
        self.logger.info("Stopping simulation...")
        self._stop_event.set()
        
        # Wait with timeout
        self._simulation_thread.join(timeout=5.0)
        if self._simulation_thread.is_alive():
            self.logger.warning("Simulation thread did not stop cleanly")
        
        self._simulation_thread = None
        self.experiment.stop()
        self.logger.info("Simulation stopped")
        
    def _run_simulation(self):
        """Main simulation loop with improved timing and error handling."""
        try:
            self.experiment.start()
            
            update_interval = self.config.measurement_interval_mins * 60  # seconds
            update_interval /= self.time_acceleration
            
            self._last_update = time.time()
            
            while not self._stop_event.is_set():
                current_time = time.time()
                elapsed = current_time - self._last_update
                
                if elapsed >= update_interval:
                    try:
                        self._update_simulation()
                        self._last_update = current_time
                    except Exception as e:
                        self.logger.error(f"Update error: {str(e)}")
                        if not isinstance(e, (ValueError, RuntimeError)):
                            raise  # Re-raise unexpected errors
                
                # Prevent CPU spinning
                time.sleep(min(0.1, update_interval / 10))
                
        except Exception as e:
            self.logger.error(f"Simulation error: {str(e)}")
            self.data_logger.log_event('error', {'message': str(e)})
            self.experiment.stop()
        finally:
            if self.experiment._status != "stopped":
                self.experiment.stop()
                
    def _update_simulation(self):
        """Single simulation update with improved error checking."""
        # Update growth models
        od_sensor = self.device._od_sensor
        for vial in range(1, self.config.device_config.n_vials + 1):
            model = od_sensor._growth_models[vial]
            model.update(
                timestep_mins=self.config.measurement_interval_mins / self.time_acceleration
            )
        
        # Update experiment
        self.experiment.update()
        
        # Log status
        status = self.experiment.status
        for vial, data in status['cultures'].items():
            self.logger.debug(
                f"Vial {vial}: OD={data['od']:.3f}, "
                f"Drug={data.get('drug_concentration', 0.0):.1f}"
            )
            
            self.data_logger.log_measurement(
                vial=vial,
                od=data['od'],
                temperature=data.get('temperature', 37.0),
                drug_concentration=data.get('drug_concentration', 0.0),
                growth_rate=data.get('growth_rate'),
                action=data.get('last_action')
            )
        
        if status['error']:
            self.data_logger.log_event('error', {'message': status['error']})