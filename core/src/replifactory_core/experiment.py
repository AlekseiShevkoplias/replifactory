from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import json

from .culture import Culture, CultureConfig
from .base_device import BaseDevice, BaseDeviceConfig
from .interfaces import DeviceError
from .protocols import GrowthControlProtocol, MorbidostatProtocol, MorbidostatConfig

@dataclass
class ExperimentConfig:
    """Configuration for experiment control.
    
    Attributes:
        measurement_interval_mins: Time between measurements
        max_generations: Stop experiment after this many generations
        max_duration_hours: Stop experiment after this many hours
        culture_config: Configuration applied to all cultures
        device_config: Device configuration
    """
    measurement_interval_mins: int = 10
    max_generations: Optional[float] = None
    max_duration_hours: Optional[float] = None
    culture_config: CultureConfig = CultureConfig()
    device_config: BaseDeviceConfig = BaseDeviceConfig()

class Experiment:
    """Coordinates multiple bacterial cultures in an evolution experiment.
    
    Manages multiple cultures, scheduling measurements and dilutions
    according to the experimental protocol.
    
    Args:
        device: Device interface for hardware control
        config: Experiment parameters
        name: Optional experiment identifier
    """
    
    def __init__(
        self,
        device: BaseDevice,
        config: ExperimentConfig = ExperimentConfig(),
        name: Optional[str] = None,
        protocol: Optional[GrowthControlProtocol] = None
    ):
        self.name = name or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.config = config
        self._device = device
        self._start_time = datetime.now()
        
        # Initialize protocol
        self.protocol = protocol or MorbidostatProtocol(MorbidostatConfig())
        
        # Initialize cultures
        self.cultures: Dict[int, Culture] = {}
        for vial in range(1, self.config.device_config.n_vials + 1):
            self.cultures[vial] = Culture(
                vial=vial,
                device=device,
                config=config.culture_config
            )
        
        self._status = "initialized"
        self._error: Optional[str] = None
        
    def start(self) -> None:
        """Start the experiment.
        
        Initializes all cultures and begins measurement cycle.
        
        Raises:
            DeviceError: If device initialization fails
            RuntimeError: If experiment already running
        """
        if self._status == "running":
            raise RuntimeError("Experiment already running")
            
        try:
            # Take initial measurements
            for culture in self.cultures.values():
                culture.measure()
                
            self._status = "running"
            self._start_time = datetime.now()
            self._error = None
            
        except Exception as e:
            self._status = "error"
            self._error = str(e)
            raise

    def stop(self) -> None:
        """Stop the experiment.
        
        Stops all device operations and sets experiment to stopped state.
        """
        try:
            self._device.emergency_stop()
        except DeviceError as e:
            self._error = f"Error during stop: {str(e)}"
            
        self._status = "stopped"

    def pause(self) -> None:
        """Pause the experiment.
        
        Temporarily suspends operations while maintaining state.
        """
        if self._status != "running":
            raise RuntimeError(f"Cannot pause experiment in {self._status} state")
            
        self._status = "paused"

    def resume(self) -> None:
        """Resume a paused experiment."""
        if self._status != "paused":
            raise RuntimeError(f"Cannot resume experiment in {self._status} state")
            
        self._status = "running"

    def update(self) -> None:
        """Perform one update cycle using configured protocol."""
        if self._status != "running":
            return
        
        try:
            # Update each culture using protocol
            for culture in self.cultures.values():
                self.protocol.update(culture)
                
            self._check_end_conditions()
                
        except Exception as e:
            self._status = "error"
            self._error = str(e)
            raise

    def _check_end_conditions(self) -> None:
        """Check if experiment should end based on config."""
        if self.config.max_generations:
            max_gens = max(c.generations for c in self.cultures.values())
            if max_gens >= self.config.max_generations:
                self.stop()
                
        if self.config.max_duration_hours:
            duration = (datetime.now() - self._start_time).total_seconds() / 3600
            if duration >= self.config.max_duration_hours:
                self.stop()

    @property
    def status(self) -> Dict:
        """Get current experiment status."""
        return {
            'name': self.name,
            'status': self._status,
            'error': self._error,
            'start_time': self._start_time.isoformat(),
            'duration_hours': (datetime.now() - self._start_time).total_seconds() / 3600,
            'cultures': {
                vial: culture.status 
                for vial, culture in self.cultures.items()
            }
        }

    def save_state(self, filename: str) -> None:
        """Save experiment state to file.
        
        Args:
            filename: Path to save state file
        """
        state = {
            'name': self.name,
            'config': self.config.__dict__,
            'status': self.status,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(state, f, indent=2)

    @classmethod
    def load_state(cls, filename: str, device: BaseDevice) -> 'Experiment':
        """Load experiment from saved state.
        
        Args:
            filename: Path to state file
            device: Device interface to use
            
        Returns:
            Reconstructed Experiment instance
        """
        with open(filename) as f:
            state = json.load(f)
            
        config = ExperimentConfig(**state['config'])
        exp = cls(device=device, config=config, name=state['name'])
        
        # Restore status
        exp._status = state['status']['status']
        exp._error = state['status']['error']
        exp._start_time = datetime.fromisoformat(state['status']['start_time'])
        
        return exp 