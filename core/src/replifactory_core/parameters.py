from dataclasses import dataclass
from enum import Enum
from typing import Optional

@dataclass
class VialMeasurements:
    """Container for measurements from a single vial.
    
    Contains all measurements that can be taken from a vial at a single point in time.
    Used to group measurements and handle missing/failed readings gracefully.
    
    Attributes:
        od: Optical density measurement
        temperature: Temperature in Celsius
        rpm: Stirrer speed in rotations per minute (None if not available)
        growth_rate: Calculated growth rate in 1/hour (None if not enough data)
        signal_mv: Raw photodiode signal in millivolts (None if not relevant)
        blank_mv: Calibration blank reading in millivolts (None if not set)
        
    Note:
        - Only od and temperature are required
        - Other fields may be None if measurement failed or isn't available
        - signal_mv and blank_mv are for OD measurement diagnostics
    """
    od: float
    temperature: float
    rpm: Optional[float] = None
    growth_rate: Optional[float] = None 
    signal_mv: Optional[float] = None
    blank_mv: Optional[float] = None

    def __post_init__(self):
        """Validate measurements after initialization."""
        if self.od < 0:
            raise ValueError("OD cannot be negative")
        if self.temperature < 0 or self.temperature > 50:
            raise ValueError("Temperature out of valid range (0-50°C)")
        if self.rpm is not None and self.rpm < 0:
            raise ValueError("RPM cannot be negative")
        if self.signal_mv is not None and self.signal_mv < 0:
            raise ValueError("Signal voltage cannot be negative")
        if self.blank_mv is not None and self.blank_mv < 0:
            raise ValueError("Blank voltage cannot be negative")

@dataclass
class PumpParameters:
    """Parameters defining pump operational characteristics.
    
    Attributes:
        max_volume_ml: Maximum volume in ml that can be pumped in one operation
        min_volume_ml: Minimum volume in ml that can be reliably pumped
        flow_rate_mlps: Flow rate in milliliters per second
    
    Note:
        These parameters are used for both real and simulated pumps to ensure
        consistent behavior across implementations.
    """
    max_volume_ml: float 
    min_volume_ml: float
    flow_rate_mlps: float  


@dataclass
class ODParameters:
    """Parameters for optical density measurements.
    
    These settings control the sensitivity and accuracy of OD readings.
    
    Attributes:
        gain: Amplification factor for photodiode signal (1, 2, 4, or 8)
            Higher gain for low OD samples, lower for high OD
        bitrate: ADC resolution in bits (12, 14, 16, or 18)
            Higher bitrate gives better precision but slower readings
        continuous_conversion: If True, ADC runs continuously
        samples_to_average: Number of samples to take and average
    """
    gain: int = 8
    bitrate: int = 16
    continuous_conversion: bool = False
    samples_to_average: int = 3


@dataclass
class LaserParameters:
    """Parameters for laser operation.
    
    Controls laser behavior during measurements.
    
    Attributes:
        warmup_time_ms: Time to wait after laser on before reading
        measurement_time_ms: Duration of measurement
        cooldown_time_ms: Time to wait between measurements
    """
    warmup_time_ms: int = 20
    measurement_time_ms: int = 100
    cooldown_time_ms: int = 50


@dataclass
class StirrerParameters:
    """Parameters for stirrer operation.
    
    Defines stirring behavior for different modes.
    
    Attributes:
        high_speed_duty_cycle: PWM duty cycle for normal operation (0-1)
        low_speed_duty_cycle: PWM duty cycle for measurement (0-1)
        acceleration_time_ms: Time to reach target speed
    """
    high_speed_duty_cycle: float = 0.8
    low_speed_duty_cycle: float = 0.3
    acceleration_time_ms: int = 100


@dataclass
class MeasurementParameters:
    """Combined parameters for all measurement operations.
    
    Collects all measurement-related parameters in one place.
    
    Attributes:
        od: Optical density measurement parameters
        laser: Laser operation parameters
        stirrer: Stirrer behavior parameters
        wait_for_steady_state: If True, verify readings are stable
        max_retries: Number of measurement retries on error
    """
    od: ODParameters = ODParameters()
    laser: LaserParameters = LaserParameters()
    stirrer: StirrerParameters = StirrerParameters()
    wait_for_steady_state: bool = True
    max_retries: int = 3