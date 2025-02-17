from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np 
import logging

logger = logging.getLogger(__name__)

from .interfaces import (
    ExperimentDeviceInterface,
    PumpInterface,
    ValveInterface,
    StirrerInterface,
    ODSensorInterface,
    ThermometerInterface,
    VialMeasurements,
    DeviceError
)

from .parameters import *


@dataclass
class BaseDeviceConfig:
    """Configuration for BaseDevice.
    
    Attributes:
        n_vials: Number of vials in device
        max_volume_ml: Maximum vial volume in ml
        min_volume_ml: Minimum operating volume in ml
    """
    n_vials: int = 7
    max_volume_ml: float = 30.0
    min_volume_ml: float = 5.0


class BaseDevice(ExperimentDeviceInterface):
    """Base implementation of experiment device control.
    
    Coordinates multiple device components to perform experiment operations.
    All hardware-specific implementation is delegated to injected components.
    
    Args:
        config: Device configuration
        pumps: Dict mapping pump numbers to pump interfaces
        valves: Valve control interface
        stirrer: Stirrer control interface
        od_sensor: OD measurement interface
        thermometer: Temperature measurement interface
    """
    
    def __init__(
        self,
        config: BaseDeviceConfig,
        pumps: Dict[int, PumpInterface],
        valves: ValveInterface,
        stirrer: StirrerInterface,
        od_sensor: ODSensorInterface,
        thermometer: ThermometerInterface,
    ):
        self.config = config
        self._pumps = pumps
        self._valves = valves
        self._stirrer = stirrer
        self._od_sensor = od_sensor
        self._thermometer = thermometer
        
        # Validate configuration
        self._validate_components()

    def _validate_components(self) -> None:
        """Validate device configuration and components.
        
        Raises:
            ValueError: If configuration is invalid
            DeviceError: If components are missing or misconfigured
        """
        if not (1 <= self.config.n_vials <= 7):
            raise ValueError(f"Invalid number of vials: {self.config.n_vials}")
            
        required_pumps = {1, 2, 4}  # Media, drug, waste
        if not all(p in self._pumps for p in required_pumps):
            raise DeviceError(f"Missing required pumps: {required_pumps - set(self._pumps)}")

    def measure_vial(self, vial: int) -> VialMeasurements:
        logger.debug(f"Starting measurement for vial {vial}")
        if not 1 <= vial <= self.config.n_vials:
            raise ValueError(f"Invalid vial number: {vial}")
            
        try:
            # Set stirrer to measurement speed
            logger.debug("Setting stirrer to low speed")
            self._stirrer.set_speed(vial, "low")
            
            # Take measurements
            logger.debug("Taking OD measurement")
            od, signal = self._od_sensor.measure_od(vial)
            logger.debug(f"OD measurement complete: {od:.3f}")
            
            logger.debug("Taking temperature measurement")
            temp = self._thermometer.measure_temperature()['vials']
            logger.debug(f"Temperature measurement complete: {temp:.1f}")
            
            logger.debug("Measuring RPM")
            rpm = self._stirrer.measure_rpm(vial)
            logger.debug(f"RPM measurement complete: {rpm}")
            
            # Restore stirrer speed
            logger.debug("Restoring stirrer to high speed")
            self._stirrer.set_speed(vial, "high")
            
            measurements = VialMeasurements(
                od=od,
                temperature=temp,
                rpm=rpm
            )
            logger.debug(f"Measurement complete for vial {vial}: {measurements}")
            return measurements
            
        except Exception as e:
            # Ensure stirrer restored on error
            logger.error(f"Error during measurement: {str(e)}")
            self._stirrer.set_speed(vial, "high")
            raise DeviceError(f"Measurement failed: {str(e)}")

    def make_dilution(self, vial: int, media_volume: float, drug_volume: float) -> None:
        """Perform dilution operation on specific vial.
        
        Args:
            vial: Vial number (1-7)
            media_volume: Volume of fresh media to add in ml
            drug_volume: Volume of drug solution to add in ml
            
        Raises:
            ValueError: If parameters invalid
            DeviceError: If operation fails
        """
        if not 1 <= vial <= self.config.n_vials:
            raise ValueError(f"Invalid vial number: {vial}")
            
        # Validate volumes
        total_volume = media_volume + drug_volume
        if total_volume > self.config.max_volume_ml:
            raise ValueError(f"Total volume {total_volume} exceeds maximum {self.config.max_volume_ml}")
            
        try:
            # Calculate new drug concentration
            current_volume = 12.0  # TODO: Get from config
            total_volume = current_volume + media_volume + drug_volume
            
            if hasattr(self._od_sensor, 'update_drug_concentration'):
                new_concentration = (drug_volume / total_volume) * 100.0  # Assuming 100x stock
                self._od_sensor.update_drug_concentration(vial, new_concentration)
            
            # Remove waste volume
            self._valves.open(vial)
            self._pumps[4].pump(total_volume)  # Waste pump
            
            # Add fresh media
            if media_volume > 0:
                self._pumps[1].pump(media_volume)  # Media pump
                
            # Add drug
            if drug_volume > 0:
                self._pumps[2].pump(drug_volume)  # Drug pump
                
        except Exception as e:
            self.emergency_stop()
            raise DeviceError(f"Dilution failed: {str(e)}")
            
        finally:
            self._valves.close(vial)

    def emergency_stop(self) -> None:
        """Emergency stop all device operations."""
        try:
            # Stop all moving parts
            for pump in self._pumps.values():
                pump.stop()
            self._stirrer.stop_all()
            
            # Close all valves
            self._valves.close_all()
            
        except Exception as e:
            # Log but don't raise - must try all stop operations
            print(f"Error during emergency stop: {str(e)}")

    @property
    def vial_status(self) -> Dict[int, Dict[str, float]]:
        """Get current status of all vials."""
        status = {}
        for vial in range(1, self.config.n_vials + 1):
            try:
                measurements = self.measure_vial(vial)
                status[vial] = {
                    'od': measurements.od,
                    'temperature': measurements.temperature,
                    'rpm': measurements.rpm if measurements.rpm else 0.0
                }
            except Exception as e:
                # Include error indication in status
                status[vial] = {
                    'od': -1.0,
                    'temperature': -1.0,
                    'rpm': -1.0,
                    'error': str(e)
                }
        return status

    def activate_pump(self, pump_id: int, volume: float) -> None:
        """Activate a pump to dispense the specified volume.
        
        Args:
            pump_id: The pump number to activate
            volume: Volume to pump in mL
            
        Raises:
            ValueError: If pump_id is invalid
            DeviceError: If pump operation fails
        """
        if pump_id not in self._pumps:
            raise ValueError(f"Invalid pump number: {pump_id}")
            
        try:
            self._pumps[pump_id].pump(volume)
        except Exception as e:
            raise DeviceError(f"Pump operation failed: {str(e)}")

    def set_valve_state(self, valve_id: int, state: bool) -> None:
        """Set the state of a valve.
        
        Args:
            valve_id: The valve number to control
            state: True to open, False to close
            
        Raises:
            ValueError: If valve_id is invalid
            DeviceError: If valve operation fails
        """
        if not 1 <= valve_id <= self.config.n_vials:
            raise ValueError(f"Invalid valve number: {valve_id}")
            
        try:
            if state:
                self._valves.open(valve_id)
            else:
                self._valves.close(valve_id)
        except Exception as e:
            raise DeviceError(f"Valve operation failed: {str(e)}")