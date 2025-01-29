from dataclasses import dataclass
import time
from typing import Dict, Optional, Tuple

import numpy as np

from replifactory_core.interfaces import (
    PumpInterface, ValveInterface, StirrerInterface,
    ODSensorInterface, ThermometerInterface, StirrerSpeed,
    DeviceError
)
from replifactory_core.parameters import ODParameters

from .growth_model import GrowthModel


@dataclass
class SimulatedPump(PumpInterface):    
    pump_number: int
    flow_rate_mlps: float = 1.0
    
    def __post_init__(self):
        self._is_pumping = False
        self._volume_pumped = 0.0
        self._lock = threading.Lock()  # Add lock for thread safety
    
    def pump(self, volume_ml: float) -> None:
        if not self._lock.acquire(blocking=False):  # Try to acquire lock
            raise DeviceError("Pump already in use")
        
        try:
            self._is_pumping = True
            duration = abs(volume_ml) / self.flow_rate_mlps
            time.sleep(duration)  # Simulate pumping time
            self._volume_pumped += volume_ml
        finally:
            self._is_pumping = False
            self._lock.release()
    
    def stop(self) -> None:
        self._is_pumping = False
    
    @property
    def is_pumping(self) -> bool:
        return self._is_pumping
    
    @property
    def pumped_volume(self) -> float:
        return self._volume_pumped


class SimulatedValves(ValveInterface):
    def __init__(self):
        self._states = {i: False for i in range(1, 8)}  # False = closed
    
    def open(self, valve_number: int) -> None:
        if not 1 <= valve_number <= 7:
            raise ValueError(f"Invalid valve number: {valve_number}")
        self._states[valve_number] = True
        time.sleep(0.1)  # Simulate valve movement
    
    def close(self, valve_number: int) -> None:
        if not 1 <= valve_number <= 7:
            raise ValueError(f"Invalid valve number: {valve_number}")
        self._states[valve_number] = False
        time.sleep(0.1)  # Simulate valve movement
    
    def is_open(self, valve_number: int) -> bool:
        if not 1 <= valve_number <= 7:
            raise ValueError(f"Invalid valve number: {valve_number}")
        return self._states[valve_number]
    
    def close_all(self) -> None:
        for v in range(1, 8):
            self._states[v] = False


class SimulatedStirrer(StirrerInterface):
    def __init__(self):
        self._speeds = {i: StirrerSpeed.STOPPED for i in range(1, 8)}
        self._rpm_map = {
            StirrerSpeed.STOPPED: 0.0,
            StirrerSpeed.LOW: 400.0,
            StirrerSpeed.HIGH: 1200.0
        }
    
    def set_speed(self, vial: int, speed: StirrerSpeed) -> None:
        if not 1 <= vial <= 7:
            raise ValueError(f"Invalid vial number: {vial}")
        self._speeds[vial] = speed
        time.sleep(0.2)  # Simulate speed change
    
    def measure_rpm(self, vial: int) -> float:
        if not 1 <= vial <= 7:
            raise ValueError(f"Invalid vial number: {vial}")
        base_rpm = self._rpm_map[self._speeds[vial]]
        # Add some noise
        return base_rpm * (1 + 0.05 * (2 * np.random.random() - 1))
    
    def stop_all(self) -> None:
        for v in range(1, 8):
            self._speeds[v] = StirrerSpeed.STOPPED


class SimulatedODSensor(ODSensorInterface):
    def __init__(self):
        self._growth_models = {i: GrowthModel() for i in range(1, 8)}
        self._blanks = {i: 40.0 for i in range(1, 8)}  # mV
        
    def measure_od(self, vial: int, parameters: Optional[ODParameters] = None) -> Tuple[float, float]:
        if not 1 <= vial <= 7:
            raise ValueError(f"Invalid vial number: {vial}")
            
        model = self._growth_models[vial]
        od = model.od
        
        # Convert OD to signal with some noise
        signal_mv = self._blanks[vial] * np.exp(-od)
        signal_mv *= (1 + 0.02 * (2 * np.random.random() - 1))
        
        time.sleep(0.1)  # Simulate measurement
        return od, signal_mv
    
    def measure_blank(self, vial: int) -> float:
        if not 1 <= vial <= 7:
            raise ValueError(f"Invalid vial number: {vial}")
        time.sleep(0.1)
        return self._blanks[vial]


class SimulatedThermometer(ThermometerInterface):
    def __init__(self):
        self._temp_setpoint = 37.0
        
    def measure_temperature(self) -> Dict[str, float]:
        # Add noise to temperature
        vial_temp = self._temp_setpoint + 0.5 * (2 * np.random.random() - 1)
        board_temp = 35.0 + 0.2 * (2 * np.random.random() - 1)
        
        time.sleep(0.1)  # Simulate measurement
        return {
            'vials': vial_temp,
            'board': board_temp
        }