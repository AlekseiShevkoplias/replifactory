from abc import ABC, abstractmethod
from typing import Dict

from .interfaces import (
    PumpInterface,
    ValveInterface,
    StirrerInterface,
    ODSensorInterface,
    ThermometerInterface
)
from .base_device import BaseDevice, BaseDeviceConfig


class DeviceComponentFactory(ABC):
    """Abstract factory for creating device components.
    
    Provides interface for creating all device components.
    Concrete implementations create either real or simulated components.
    """
    
    @abstractmethod
    def create_pump(self, pump_number: int) -> PumpInterface:
        """Create a pump component.
        
        Args:
            pump_number: Identifier for the pump (1=media, 2=drug, 4=waste)
        """
        pass
    
    @abstractmethod
    def create_valves(self) -> ValveInterface:
        """Create valve control component."""
        pass
    
    @abstractmethod
    def create_stirrer(self) -> StirrerInterface:
        """Create stirrer control component."""
        pass
    
    @abstractmethod
    def create_od_sensor(self) -> ODSensorInterface:
        """Create OD measurement component."""
        pass
    
    @abstractmethod
    def create_thermometer(self) -> ThermometerInterface:
        """Create temperature measurement component."""
        pass


class DeviceFactory:
    """Factory for creating complete device instances.
    
    Creates and assembles all components into a working device.
    """
    
    @staticmethod
    def create_device(
        factory: DeviceComponentFactory,
        config: BaseDeviceConfig = BaseDeviceConfig()
    ) -> BaseDevice:
        """Create a complete device using specified component factory.
        
        Args:
            factory: Component factory (real or simulated)
            config: Device configuration
            
        Returns:
            Configured BaseDevice instance
        """
        # Create required pumps
        pumps: Dict[int, PumpInterface] = {
            1: factory.create_pump(1),  # Media pump
            2: factory.create_pump(2),  # Drug pump
            4: factory.create_pump(4)   # Waste pump
        }
        
        # Create other components
        valves = factory.create_valves()
        stirrer = factory.create_stirrer()
        od_sensor = factory.create_od_sensor()
        thermometer = factory.create_thermometer()
        
        # Assemble device
        return BaseDevice(
            config=config,
            pumps=pumps,
            valves=valves,
            stirrer=stirrer,    
            od_sensor=od_sensor,
            thermometer=thermometer
        )
