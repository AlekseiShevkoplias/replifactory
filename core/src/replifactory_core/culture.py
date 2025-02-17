from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np

from .parameters import VialMeasurements
from .base_device import BaseDevice

@dataclass
class CultureConfig:
    """Configuration for bacterial culture control.
    
    Attributes:
        od_threshold: OD level that triggers dilution
        growth_rate_threshold: Growth rate that triggers stress increase
        min_growth_rate: Growth rate below which rescue dilution occurs
        dilution_factor: Factor by which to dilute culture
        max_drug_concentration: Maximum allowed drug concentration
    """
    od_threshold: float = 0.3
    growth_rate_threshold: float = 0.15
    min_growth_rate: float = -0.1
    dilution_factor: float = 1.6
    max_drug_concentration: float = 100.0

class Culture:
    """Core culture control logic.
    
    Manages a single bacterial culture vial, coordinating measurements,
    growth tracking, and drug concentration adjustments.
    
    Args:
        vial: Vial number (1-7)
        device: Device interface for hardware control
        config: Culture control parameters
    """
    
    def __init__(
        self,
        vial: int,
        device: BaseDevice,
        config: CultureConfig = CultureConfig()
    ):
        self.vial = vial
        self._device = device
        self.config = config
        
        self._measurements: List[Tuple[datetime, VialMeasurements]] = []
        self._drug_concentrations: List[Tuple[datetime, float]] = []
        self._generations: List[Tuple[datetime, float]] = []
        
        # Initialize with zero drug concentration
        self._drug_concentrations.append((datetime.now(), 0.0))
        self._generations.append((datetime.now(), 0.0))

    def measure(self) -> VialMeasurements:
        """Take new measurements of the culture.
        
        Returns:
            VialMeasurements containing current culture state
            
        Raises:
            DeviceError: If measurements fail
        """
        measurements = self._device.measure_vial(self.vial)
        self._measurements.append((datetime.now(), measurements))
        return measurements

    def calculate_growth_rate(self, window_minutes: int = 30) -> Optional[float]:
        """Calculate current growth rate from recent measurements.
        
        Args:
            window_minutes: Time window to use for calculation
            
        Returns:
            Growth rate in 1/hour or None if insufficient data
        """
        if len(self._measurements) < 2:
            return None
            
        # Get measurements in window
        now = datetime.now()
        window_measurements = [
            (t, m) for t, m in self._measurements 
            if (now - t).total_seconds() <= window_minutes * 60
        ]
        
        if len(window_measurements) < 2:
            return None
            
        # Calculate growth rate from OD measurements
        t1, m1 = window_measurements[0]
        t2, m2 = window_measurements[-1]
        
        dt = (t2 - t1).total_seconds() / 3600  # Convert to hours
        if dt == 0:
            return None
            
        return (np.log(m2.od) - np.log(m1.od)) / dt

    def make_dilution(self, target_drug_concentration: Optional[float] = None) -> None:
        """Perform dilution with optional drug concentration adjustment.
        
        Args:
            target_drug_concentration: Desired final drug concentration.
                If None, maintains current concentration.
                
        Raises:
            ValueError: If target concentration exceeds maximum
            DeviceError: If dilution operation fails
        """
        if target_drug_concentration is None:
            target_drug_concentration = self._drug_concentrations[-1][1]
            
        if target_drug_concentration > self.config.max_drug_concentration:
            raise ValueError(f"Target concentration {target_drug_concentration} exceeds maximum {self.config.max_drug_concentration}")
            
        # Calculate volumes needed
        current_volume = 12.0  # TODO: Get from device config
        added_volume = current_volume * (self.config.dilution_factor - 1)
        
        # Calculate media and drug volumes to achieve target concentration
        if target_drug_concentration > 0:
            drug_volume = added_volume * (target_drug_concentration / self.config.max_drug_concentration)
            media_volume = added_volume - drug_volume
        else:
            drug_volume = 0
            media_volume = added_volume
            
        # Perform dilution
        self._device.make_dilution(self.vial, media_volume, drug_volume)
        
        # Update tracking
        now = datetime.now()
        self._drug_concentrations.append((now, target_drug_concentration))
        
        # Update generations
        prev_gens = self._generations[-1][1]
        new_gens = prev_gens + np.log2(self.config.dilution_factor)
        self._generations.append((now, new_gens))

    @property
    def current_od(self) -> Optional[float]:
        """Get most recent OD measurement."""
        if not self._measurements:
            return None
        return self._measurements[-1][1].od
        
    @property
    def current_drug_concentration(self) -> float:
        """Get current drug concentration."""
        return self._drug_concentrations[-1][1]
        
    @property
    def generations(self) -> float:
        """Get current number of generations."""
        return self._generations[-1][1]
        
    @property
    def status(self) -> Dict:
        """Get current culture status."""
        return {
            'od': self.current_od,
            'drug_concentration': self.current_drug_concentration,
            'generations': self.generations,
            'growth_rate': self.calculate_growth_rate(),
            'last_measurement': self._measurements[-1][0] if self._measurements else None
        } 