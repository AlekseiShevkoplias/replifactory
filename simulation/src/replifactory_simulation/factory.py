from typing import Dict, Optional

from replifactory_core.factory import DeviceComponentFactory
from replifactory_core.interfaces import (
    PumpInterface, ValveInterface, StirrerInterface,
    ODSensorInterface, ThermometerInterface
)
from replifactory_core.base_device import BaseDevice, BaseDeviceConfig

from .devices import (
    SimulatedPump, SimulatedValves, SimulatedStirrer,
    SimulatedODSensor, SimulatedThermometer
)
from .growth_model import GrowthModelParameters

class SimulationFactory(DeviceComponentFactory):
    """Factory for creating simulated device components."""
    
    def create_device(
        self, 
        config: BaseDeviceConfig,
        model_params: Optional[GrowthModelParameters] = None
    ) -> BaseDevice:
        """Create complete simulated device."""
        pumps = {
            1: self.create_pump(1),  # Media
            2: self.create_pump(2),  # Drug
            4: self.create_pump(4)   # Waste
        }
        
        return BaseDevice(
            config=config,
            pumps=pumps,
            valves=self.create_valves(),
            stirrer=self.create_stirrer(),
            od_sensor=self.create_od_sensor(model_params),
            thermometer=self.create_thermometer()
        )
    
    def create_pump(self, pump_number: int) -> PumpInterface:
        """Create simulated pump."""
        return SimulatedPump(pump_number=pump_number)
    
    def create_valves(self) -> ValveInterface:
        """Create simulated valve control."""
        return SimulatedValves()
    
    def create_stirrer(self) -> StirrerInterface:
        """Create simulated stirrer control."""
        return SimulatedStirrer()
    
    def create_od_sensor(self, model_params: Optional[GrowthModelParameters] = None) -> ODSensorInterface:
        """Create simulated OD sensor."""
        return SimulatedODSensor(model_params)
    
    def create_thermometer(self) -> ThermometerInterface:
        """Create simulated thermometer."""
        return SimulatedThermometer() 