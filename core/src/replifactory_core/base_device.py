from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np 

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
        """Get all measurements for a specific vial.
        
        Coordinates multiple measurements while handling stirrer speed.
        
        Args:
            vial: Vial number (1-7)
            
        Returns:
            VialMeasurements with all available data
            
        Raises:
            ValueError: If vial number invalid
            DeviceError: If critical measurements fail
        """
        if not 1 <= vial <= self.config.n_vials:
            raise ValueError(f"Invalid vial number: {vial}")
            
        try:
            # Set stirrer to measurement speed
            self._stirrer.set_speed(vial, "low")
            
            # Take measurements
            od, signal = self._od_sensor.measure_od(vial)
            temp = self._thermometer.measure_temperature()['vials']
            rpm = self._stirrer.measure_rpm(vial)
            
            # Restore stirrer speed
            self._stirrer.set_speed(vial, "high")
            
            return VialMeasurements(
                od=od,
                temperature=temp,
                rpm=rpm
            )
            
        except Exception as e:
            # Ensure stirrer restored on error
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