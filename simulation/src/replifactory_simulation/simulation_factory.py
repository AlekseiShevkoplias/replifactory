from replifactory_core.interfaces import (
    PumpInterface, ValveInterface, StirrerInterface,
    ODSensorInterface, ThermometerInterface
)
from replifactory_core.base_device import BaseDevice, BaseDeviceConfig
from replifactory_core.factory import DeviceComponentFactory

from .devices import (
    SimulatedPump, SimulatedValves, SimulatedStirrer,
    SimulatedODSensor, SimulatedThermometer
)


class SimulationFactory(DeviceComponentFactory):
    def __init__(self, monitor=None):
        self.monitor = monitor

    def create_pump(self, pump_number: int) -> PumpInterface:
        return SimulatedPump(
            pump_number=pump_number,
            event_listener=self.monitor
        )
    
    def create_valves(self) -> ValveInterface:
        return SimulatedValves(event_listener=self.monitor)
    
    def create_stirrer(self) -> StirrerInterface:
        return SimulatedStirrer()
    
    def create_od_sensor(self) -> ODSensorInterface:
        return SimulatedODSensor()
    
    def create_thermometer(self) -> ThermometerInterface:
        return SimulatedThermometer()


def create_simulated_device(config: BaseDeviceConfig = None, monitor=None) -> BaseDevice:
    if config is None:
        config = BaseDeviceConfig()
    
    factory = SimulationFactory(monitor=monitor)
    
    return BaseDevice(
        config=config,
        pumps={
            1: factory.create_pump(1),  # Media
            2: factory.create_pump(2),  # Drug
            4: factory.create_pump(4)   # Waste
        },
        valves=factory.create_valves(),
        stirrer=factory.create_stirrer(),
        od_sensor=factory.create_od_sensor(),
        thermometer=factory.create_thermometer()
    )