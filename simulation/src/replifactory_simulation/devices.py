from dataclasses import dataclass
import time
from typing import Dict, Optional, Tuple
import threading
import numpy as np
import logging

from replifactory_core.interfaces import (
    PumpInterface, ValveInterface, StirrerInterface,
    ODSensorInterface, ThermometerInterface, StirrerSpeed,
    DeviceError, DeviceEventListener
)
from replifactory_core.parameters import ODParameters

from .growth_model import GrowthModel, GrowthModelParameters

logger = logging.getLogger(__name__)

@dataclass
class SimulatedPump(PumpInterface):    
    pump_number: int
    flow_rate_mlps: float = 1.0
    event_listener: Optional[DeviceEventListener] = None
    
    def __post_init__(self):
        self._is_pumping = False
        self._volume_pumped = 0.0
        self._lock = threading.Lock()  # Lock for thread safety
    
    def pump(self, volume_ml: float) -> None:
        logger.debug(f"Pump {self.pump_number} attempting to pump {volume_ml}ml")
        if not self._lock.acquire(blocking=False):  # Try to acquire lock
            raise DeviceError("Pump already in use")
        
        try:
            self._is_pumping = True
            if self.event_listener:
                self.event_listener.on_pump_status_change(self.pump_number, True)
            
            duration = abs(volume_ml) / self.flow_rate_mlps
            logger.debug(f"Pump {self.pump_number} pumping for {duration:.2f}s")
            time.sleep(duration)  # Simulate pumping time
            self._volume_pumped += volume_ml
            logger.debug(f"Pump {self.pump_number} finished pumping")
        finally:
            self._is_pumping = False
            if self.event_listener:
                self.event_listener.on_pump_status_change(self.pump_number, False)
            self._lock.release()
    
    def stop(self) -> None:
        logger.debug(f"Stopping pump {self.pump_number}")
        self._is_pumping = False
    
    @property
    def is_pumping(self) -> bool:
        return self._is_pumping
    
    @property
    def pumped_volume(self) -> float:
        return self._volume_pumped

    def activate_pump(self, pump_id: int, volume_ul: float):
        """Activate a pump to dispense the specified volume."""
        if not 1 <= pump_id <= self.pump_number:
            raise ValueError(f"Invalid pump number: {pump_id}")
            
        # Emit pump active status
        self.monitor.emit_pump_status(pump_id, True)
        
        # Simulate pumping time
        time.sleep(volume_ul * 0.001)  # 1ms per µL
        
        # Emit pump inactive status
        self.monitor.emit_pump_status(pump_id, False)


class SimulatedValves(ValveInterface):
    def __init__(self, event_listener: Optional[DeviceEventListener] = None):
        self._states = {i: False for i in range(1, 8)}  # False = closed
        self.event_listener = event_listener
        logger.debug("Initialized valve states")
    
    def open(self, valve_number: int) -> None:
        logger.debug(f"Opening valve {valve_number}")
        if not 1 <= valve_number <= 7:
            raise ValueError(f"Invalid valve number: {valve_number}")
        self._states[valve_number] = True
        if self.event_listener:
            self.event_listener.on_valve_status_change(valve_number, True)
        time.sleep(0.1)  # Simulate valve movement
    
    def close(self, valve_number: int) -> None:
        logger.debug(f"Closing valve {valve_number}")
        if not 1 <= valve_number <= 7:
            raise ValueError(f"Invalid valve number: {valve_number}")
        self._states[valve_number] = False
        if self.event_listener:
            self.event_listener.on_valve_status_change(valve_number, False)
        time.sleep(0.1)  # Simulate valve movement
    
    def is_open(self, valve_number: int) -> bool:
        if not 1 <= valve_number <= 7:
            raise ValueError(f"Invalid valve number: {valve_number}")
        return self._states[valve_number]
    
    def close_all(self) -> None:
        logger.debug("Closing all valves")
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
        logger.debug("Initialized stirrer speeds")
    
    def set_speed(self, vial: int, speed: StirrerSpeed) -> None:
        logger.debug(f"Setting vial {vial} stirrer to {speed}")
        if not 1 <= vial <= 7:
            raise ValueError(f"Invalid vial number: {vial}")
        self._speeds[vial] = speed
        time.sleep(0.2)  # Simulate speed change
    
    def measure_rpm(self, vial: int) -> float:
        logger.debug(f"Measuring RPM for vial {vial}")
        if not 1 <= vial <= 7:
            raise ValueError(f"Invalid vial number: {vial}")
        base_rpm = self._rpm_map[self._speeds[vial]]
        # Add some noise
        rpm = base_rpm * (1 + 0.05 * (2 * np.random.random() - 1))
        logger.debug(f"Vial {vial} RPM: {rpm:.1f}")
        return rpm
    
    def stop_all(self) -> None:
        logger.debug("Stopping all stirrers")
        for v in range(1, 8):
            self._speeds[v] = StirrerSpeed.STOPPED


class SimulatedODSensor(ODSensorInterface):
    """Simulates bacterial growth and OD measurements."""
    
    def __init__(self, model_params: Optional[GrowthModelParameters] = None):
        # Initialize growth models for each vial
        self._growth_models = {
            i: GrowthModel(parameters=model_params)
            for i in range(1, 8)
        }
        
        # Blank values for each vial
        self.blank_values = {i: 1000.0 for i in range(1, 8)}  # mV
        logger.debug("Initialized OD sensor with growth models")
        
    def measure_blank(self, vial: int) -> float:
        """Measure blank (empty vial) signal."""
        logger.debug(f"Measuring blank for vial {vial}")
        if not 1 <= vial <= 7:
            raise ValueError(f"Invalid vial number: {vial}")
            
        # Add some noise to the blank measurement
        blank = self.blank_values[vial] * (1 + 0.005 * np.random.randn())
        time.sleep(0.1)  # Simulate measurement time
        logger.debug(f"Vial {vial} blank: {blank:.1f}mV")
        return blank
        
    def measure_od(self, vial: int, parameters: Optional[ODParameters] = None) -> Tuple[float, float]:
        logger.debug(f"Measuring OD for vial {vial}")
        if not 1 <= vial <= 7:
            raise ValueError(f"Invalid vial number: {vial}")
            
        # Get current OD from growth model
        model = self._growth_models[vial]
        
        # Add measurement noise
        measured_od = model.od * (1 + 0.02 * np.random.randn())
        signal = 1000 * np.exp(-measured_od) * (1 + 0.01 * np.random.randn())
        
        time.sleep(0.1)  # Simulate measurement time
        logger.debug(f"Vial {vial} OD: {measured_od:.3f}, Signal: {signal:.1f}mV")
        return measured_od, signal
        
    def update_drug_concentration(self, vial: int, concentration: float):
        """Update drug concentration after dilution."""
        logger.debug(f"Updating vial {vial} drug concentration to {concentration}")
        if not 1 <= vial <= 7:
            raise ValueError(f"Invalid vial number: {vial}")
            
        model = self._growth_models[vial]
        model.drug_concentration = concentration


class SimulatedThermometer(ThermometerInterface):
    def __init__(self):
        self._temp_setpoint = 37.0
        logger.debug("Initialized thermometer")
        
    def measure_temperature(self) -> Dict[str, float]:
        logger.debug("Measuring temperatures")
        # Add noise to temperature
        vial_temp = self._temp_setpoint + 0.5 * (2 * np.random.random() - 1)
        board_temp = 35.0 + 0.2 * (2 * np.random.random() - 1)
        
        time.sleep(0.1)  # Simulate measurement
        logger.debug(f"Temperatures - Vials: {vial_temp:.1f}°C, Board: {board_temp:.1f}°C")
        return {
            'vials': vial_temp,
            'board': board_temp
        }

