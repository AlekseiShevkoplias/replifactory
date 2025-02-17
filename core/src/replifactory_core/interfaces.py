from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple, List

from .parameters import *


class DeviceError(Exception):
    """Base exception for device-related errors."""
    pass


class StirrerSpeed(str, Enum):
    """Enumeration of valid stirrer speeds.
    
    STOPPED: Motor off
    LOW: Low speed for measurement
    HIGH: Normal operating speed
    """
    STOPPED = "stopped"
    LOW = "low"
    HIGH = "high"


class PumpInterface(ABC):
    """Interface for controlling fluid pumps in the device.
    
    Provides high-level control of pumping operations while abstracting away
    hardware details like stepper motors or peristaltic mechanisms.
    
    A pump must maintain accurate volume tracking and provide immediate
    stop capability for safety.
    
    Typical usage:
        pump.pump(5.0)  # Pump 5ml
        if pump.is_pumping:
            pump.stop()  # Emergency stop
    """
    
    @abstractmethod
    def pump(self, volume_ml: float) -> None:
        """Pump a specific volume of fluid.
        
        Args:
            volume_ml: Volume to pump in milliliters. Positive values pump forward,
                      negative values pump in reverse if supported.
        
        Raises:
            ValueError: If volume exceeds pump parameters
            DeviceError: If pump operation fails
        
        Note:
            Method should block until pumping is complete unless stopped.
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Immediately stop the pump.
        
        Emergency stop that halts the pump as quickly as possible without
        regard for completing the current operation.
        
        The pumped_volume property should reflect the actual delivered volume.
        
        Raises:
            DeviceError: If pump fails to stop
        """
        pass

    @property
    @abstractmethod
    def is_pumping(self) -> bool:
        """Check if pump is currently active.
        
        Returns:
            bool: True if pump is in operation, False if idle
            
        Note: 
            Should return True from the moment pump() is called until 
            the operation completes or is stopped.
        """
        pass

    @property
    @abstractmethod
    def pumped_volume(self) -> float:
        """Get total volume pumped since last reset.
        
        Returns:
            float: Cumulative volume in milliliters, including partial volumes
                  from stopped operations
                  
        Note:
            Tracking should continue across multiple pump operations until reset.
        """
        pass


class ValveInterface(ABC):
    """Interface for controlling liquid flow valves.
    
    Controls individual solenoid valves that direct fluid flow in the device.
    Each valve has a unique number and binary open/closed state.
    
    Valves are critical for fluid routing and provide safety isolation.
    All implementations must ensure reliable state reporting and 
    fail-closed behavior.
    
    Typical usage:
        valve.open(1)   # Open valve 1
        if valve.is_open(1):
            valve.close(1)
    """
    
    @abstractmethod
    def open(self, valve_number: int) -> None:
        """Open a specific valve.
        
        Args:
            valve_number: Identifier of the valve (1-7)
            
        Raises:
            ValueError: If valve_number is invalid (not 1-7)
            DeviceError: If valve fails to open or verify state
            
        Note:
            Method should block until valve is fully open and verified.
        """
        pass

    @abstractmethod
    def close(self, valve_number: int) -> None:
        """Close a specific valve.
        
        Args:
            valve_number: Identifier of the valve (1-7)
            
        Raises:
            ValueError: If valve_number is invalid
            DeviceError: If valve fails to close or verify state
            
        Note:
            Method must ensure valve is fully closed before returning.
            Should never fail to at least attempt closure for safety.
        """
        pass

    @abstractmethod
    def is_open(self, valve_number: int) -> bool:
        """Check if specific valve is open.
        
        Args:
            valve_number: Identifier of the valve (1-7)
            
        Returns:
            bool: True if valve is confirmed open, False if confirmed closed
            
        Raises:
            ValueError: If valve_number is invalid
            DeviceError: If valve state cannot be determined
            
        Note:
            Must return accurate state - if state cannot be verified,
            should raise DeviceError rather than guess.
        """
        pass

    @abstractmethod
    def close_all(self) -> None:
        """Close all valves immediately.
        
        Critical safety method - must attempt to close all valves even if
        some operations fail. Should be called in any error condition.
        
        Raises:
            DeviceError: If any valve fails to close. Error should include
                        information about which valves failed.
                        
        Note:
            Should make best effort to close all valves even after errors.
        """
        pass


class StirrerInterface(ABC):
    """Interface for controlling magnetic stirrers.
    
    Manages the stirring motors that mix cultures via magnetic stir bars.
    Supports variable speeds and rotation monitoring.
    
    Speed control is critical for:
    - Proper culture mixing
    - Accurate OD measurements (requires LOW speed)
    - Prevention of vortexing (speed limits)
    
    Implementation must ensure smooth speed transitions and
    accurate RPM reporting when available.
    
    Typical usage:
        stirrer.set_speed(1, StirrerSpeed.HIGH)  # Normal operation
        rpm = stirrer.measure_rpm(1)             # Check actual speed
        stirrer.set_speed(1, StirrerSpeed.LOW)   # Prepare for measurement
    """
    
    @abstractmethod
    def set_speed(self, vial: int, speed: StirrerSpeed) -> None:
        """Set stirrer speed for a specific vial.
        
        Args:
            vial: Vial number (1-7)
            speed: Desired stirring speed setting
            
        Raises:
            ValueError: If vial number invalid or speed not in StirrerSpeed
            DeviceError: If speed cannot be set or verified
            
        Note:
            Should transition smoothly between speeds to avoid splashing.
            Must verify speed change before returning.
        """
        pass
    
    @abstractmethod
    def measure_rpm(self, vial: int) -> float:
        """Measure current RPM for specific vial.
        
        Args:
            vial: Vial number (1-7)
            
        Returns:
            float: Current stirring speed in rotations per minute
            
        Raises:
            ValueError: If vial number invalid
            DeviceError: If RPM cannot be measured
            
        Note:
            May return approximate RPM if exact measurement not possible.
            Should indicate measurement quality through error bounds.
        """
        pass

    @abstractmethod
    def stop_all(self) -> None:
        """Emergency stop all stirrers.
        
        Immediately stops all stirring motors. Used in emergency situations
        or during shutdown.
        
        Raises:
            DeviceError: If any stirrer fails to stop. Should still attempt
                        to stop all stirrers even after an error.
                        
        Note:
            Must attempt to stop all stirrers regardless of errors.
            Critical safety method.
        """
        pass


class ODSensorInterface(ABC):
    """Interface for optical density measurement system.
    
    Manages laser-based optical density measurements for monitoring bacterial growth.
    Coordinates laser control and photodiode readings to produce accurate OD values.
    
    Key responsibilities:
    - Accurate OD measurements
    - Blank calibration
    - Signal quality monitoring
    - Laser safety management
    
    Implementation must ensure:
    - Laser safety interlocks
    - Proper measurement timing
    - Signal stability checking
    - Background light compensation
    
    Typical usage:
        od, signal = sensor.measure_od(1)  # Get current OD
        blank = sensor.measure_blank(1)    # Calibration measurement
    """
    
    @abstractmethod
    def measure_od(self, vial: int, parameters: Optional[ODParameters] = None) -> Tuple[float, float]:
        """Measure optical density for specific vial.
        
        Performs a complete OD measurement cycle:
        1. Set stirrer to measurement speed
        2. Turn on laser
        3. Take photodiode reading
        4. Turn off laser
        5. Restore stirrer speed
        
        Args:
            vial: Vial number (1-7)
            parameters: Optional measurement parameters. Uses defaults if None.
            
        Returns:
            Tuple[float, float]: (od_value, signal_strength)
                od_value: Calculated optical density (relative to blank)
                signal_strength: Raw photodiode signal in millivolts
                
        Raises:
            ValueError: If vial number invalid
            DeviceError: If measurement fails (laser, photodiode, or signal quality)
            
        Note:
            Returns both OD and raw signal to allow signal quality assessment.
            Should verify signal stability before returning.
        """
        pass

    @abstractmethod
    def measure_blank(self, vial: int) -> float:
        """Measure blank/reference value for calibration.
        
        Takes reference measurement of clear media for OD calculation baseline.
        Must be called on each vial before experiment starts.
        
        Args:
            vial: Vial number (1-7)
            
        Returns:
            float: Blank reading in millivolts
            
        Raises:
            ValueError: If vial number invalid
            DeviceError: If measurement fails or signal unstable
            
        Note:
            Should take multiple readings and verify stability.
            Critical for accurate OD measurements.
        """
        pass


class ThermometerInterface(ABC):
    """Interface for temperature monitoring system.
    
    Manages temperature sensors for both culture vials and control board.
    Temperature monitoring is critical for:
    - Culture growth conditions
    - Hardware protection
    - Safety cutoffs
    
    Implementation must provide reliable temperature data and
    proper error handling for sensor failures.
    
    Typical usage:
        temps = thermometer.measure_temperature()
        vial_temp = temps['vials']
        board_temp = temps['board']
    """
    
    @abstractmethod
    def measure_temperature(self) -> Dict[str, float]:
        """Measure all system temperatures.
        
        Returns:
            Dict[str, float]: Temperature readings in Celsius
                'vials': Average temperature of vial array
                'board': Control board temperature
                
        Raises:
            DeviceError: If temperature measurements fail or are out of range
            
        Note:
            Should include validity checks on temperature values.
            Must handle partial sensor failures gracefully.
        """
        pass


class ExperimentDeviceInterface(ABC):
    """High-level interface for experiment control.
    
    Provides experiment-focused operations that coordinate multiple device
    components. This is the primary interface used by experiment control logic.
    
    Responsible for:
    - Measurement coordination
    - Dilution operations
    - Status monitoring
    - Emergency handling
    
    Implementation must ensure:
    - Operation atomicity
    - Error recovery
    - Data consistency
    - Safe state management
    
    Typical usage:
        measurements = device.measure_vial(1)
        device.make_dilution(1, media_ml=5.0, drug_ml=0.5)
        status = device.vial_status
    """
    
    @abstractmethod
    def measure_vial(self, vial: int) -> VialMeasurements:
        """Get all measurements for a specific vial.
        
        Performs a complete measurement cycle:
        1. Temperature reading
        2. RPM measurement if available
        3. OD measurement
        4. Growth rate calculation if possible
        
        Args:
            vial: Vial number (1-7)
            
        Returns:
            VialMeasurements: Combined measurements from vial
            
        Raises:
            ValueError: If vial number invalid
            DeviceError: If critical measurements fail
            
        Note:
            Should complete all possible measurements even if some fail.
            Critical measurements (OD) failure causes error.
        """
        pass
    
    @abstractmethod
    def make_dilution(self, vial: int, media_volume: float, drug_volume: float) -> None:
        """Perform dilution operation on specific vial.
        
        Executes complete dilution sequence:
        1. Verify volumes and vial state
        2. Remove waste volume
        3. Add fresh media
        4. Add drug solution
        5. Verify operation completion
        
        Args:
            vial: Vial number (1-7)
            media_volume: Volume of fresh media to add in ml
            drug_volume: Volume of drug solution to add in ml
            
        Raises:
            ValueError: If vial number or volumes invalid
            DeviceError: If dilution operation fails
            
        Note:
            Operation must be atomic - should revert to safe state on error.
            Must verify all steps complete successfully.
        """
        pass

    @abstractmethod
    def emergency_stop(self) -> None:
        """Emergency stop all device operations.
        
        Immediately stops all device components and sets system to safe state:
        1. Stop all pumps
        2. Close all valves
        3. Stop all stirrers
        4. Turn off all lasers
        5. Set status LEDs to error state
        
        Should be called in response to:
        - Critical errors
        - Safety interlock triggers
        - User emergency stop
        - Power issues
        
        Note:
            Most critical safety method - must be extremely reliable.
            Should attempt all steps even if some fail.
            Must log all actions and failures.
        """
        pass

    @property
    @abstractmethod
    def vial_status(self) -> Dict[int, Dict[str, float]]:
        """Get current status of all vials.
        
        Provides snapshot of system state including:
        - OD readings
        - Temperatures
        - Stirrer speeds
        - Growth rates
        
        Returns:
            Dict[int, Dict[str, float]]: Status data
                Keys: vial numbers (1-7)
                Values: dict with measurement values
                    'od': Current optical density
                    'temperature': Current temperature
                    'rpm': Current stirrer speed if available
                    'growth_rate': Current growth rate if available
        
        Note:
            Should return best available data even if some readings fail.
            Must indicate missing/failed measurements appropriately.
        """
        pass


class DeviceEventListener(ABC):
    """Interface for listening to device events."""
    
    @abstractmethod
    def on_pump_status_change(self, pump_id: int, active: bool) -> None:
        """Called when a pump's status changes."""
        pass
        
    @abstractmethod
    def on_valve_status_change(self, valve_id: int, is_open: bool) -> None:
        """Called when a valve's status changes."""
        pass