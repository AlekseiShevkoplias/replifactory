from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime
import numpy as np

from .culture import Culture
from .parameters import VialMeasurements


@dataclass
class ProtocolConfig:
    """Base configuration for growth control protocols."""
    pass


@dataclass
class MorbidostatConfig(ProtocolConfig):
    """Configuration for morbidostat control protocol.
    
    Attributes:
        od_threshold: OD level that triggers dilution
        target_growth_rate: Desired growth rate to maintain
        growth_rate_tolerance: Acceptable deviation from target
        min_growth_rate: Growth rate below which rescue dilution occurs
        max_drug_concentration: Maximum allowed drug concentration
        drug_concentration_step: Relative increase in drug concentration
        dilution_factor: Factor by which to dilute culture
        measurement_window_mins: Time window for growth rate calculation
    """
    od_threshold: float = 0.3
    target_growth_rate: float = 0.15  # hr^-1
    growth_rate_tolerance: float = 0.05
    min_growth_rate: float = -0.1
    max_drug_concentration: float = 100.0
    drug_concentration_step: float = 1.5
    dilution_factor: float = 1.6
    measurement_window_mins: int = 30


class GrowthControlProtocol(ABC):
    """Base class for growth control protocols.
    
    Defines interface for implementing different control strategies.
    """
    
    @abstractmethod
    def update(self, culture: Culture) -> Optional[Dict]:
        """Update control protocol for a culture.
        
        Args:
            culture: Culture to update
            
        Returns:
            Optional[Dict]: Control actions taken, if any
        """
        pass
    
    @abstractmethod
    def get_status(self) -> Dict:
        """Get current protocol status."""
        pass


class MorbidostatProtocol(GrowthControlProtocol):
    """Morbidostat growth control protocol.
    
    Implements feedback control to maintain constant growth rate by
    adjusting drug concentration. Core logic:
    
    1. Dilute when OD exceeds threshold
    2. If growth rate too high: increase drug concentration
    3. If growth rate too low: decrease drug concentration
    4. If growth severely inhibited: perform rescue dilution
    
    Args:
        config: Protocol configuration parameters
    """
    
    def __init__(self, config: MorbidostatConfig = MorbidostatConfig()):
        self.config = config
        self._history: List[Dict] = []
        
    def update(self, culture: Culture) -> Optional[Dict]:
        """Update morbidostat control for a culture.
        
        Implements core morbidostat logic:
        1. Calculate current growth rate
        2. Determine if dilution needed
        3. Adjust drug concentration based on growth rate
        
        Args:
            culture: Culture to update
            
        Returns:
            Dict with control actions if any were taken
        """
        # Get current measurements
        measurements = culture.measure()
        growth_rate = culture.calculate_growth_rate(
            window_minutes=self.config.measurement_window_mins
        )
        
        # Initialize response
        response = {
            'timestamp': datetime.now(),
            'od': measurements.od,
            'growth_rate': growth_rate,
            'drug_concentration': culture.current_drug_concentration,
            'action': None
        }
        
        # Check if growth rate could be calculated
        if growth_rate is None:
            self._history.append(response)
            return response
            
        # Determine control action
        action = self._determine_control_action(measurements, growth_rate)
        
        # Execute control action
        if action:
            response['action'] = action
            self._execute_control_action(culture, action)
            
        self._history.append(response)
        return response
    
    def _determine_control_action(
        self, 
        measurements: VialMeasurements, 
        growth_rate: float
    ) -> Optional[str]:
        """Determine appropriate control action based on measurements.
        
        Args:
            measurements: Current culture measurements
            growth_rate: Calculated growth rate
            
        Returns:
            String indicating control action or None if no action needed
        """
        # Check for severely inhibited growth
        if growth_rate < self.config.min_growth_rate:
            return 'rescue_dilution'
            
        # Check if OD threshold exceeded
        if measurements.od < self.config.od_threshold:
            return None
            
        # Determine drug adjustment based on growth rate
        growth_error = growth_rate - self.config.target_growth_rate
        
        if abs(growth_error) <= self.config.growth_rate_tolerance:
            return 'maintain'
        elif growth_error > 0:
            return 'increase_drug'
        else:
            return 'decrease_drug'
    
    def _execute_control_action(self, culture: Culture, action: str) -> None:
        """Execute determined control action.
        
        Args:
            culture: Culture to control
            action: Control action to execute
        """
        current_conc = culture.current_drug_concentration
        
        if action == 'rescue_dilution':
            # Perform dilution with reduced drug concentration
            new_conc = max(0, current_conc / self.config.drug_concentration_step)
            culture.make_dilution(target_drug_concentration=new_conc)
            
        elif action == 'maintain':
            # Maintain current drug concentration
            culture.make_dilution()
            
        elif action == 'increase_drug':
            # Increase drug concentration
            new_conc = min(
                self.config.max_drug_concentration,
                current_conc * self.config.drug_concentration_step
            )
            culture.make_dilution(target_drug_concentration=new_conc)
            
        elif action == 'decrease_drug':
            # Decrease drug concentration
            new_conc = current_conc / self.config.drug_concentration_step
            culture.make_dilution(target_drug_concentration=new_conc)
    
    def get_status(self) -> Dict:
        """Get current protocol status.
        
        Returns:
            Dict containing:
            - Configuration parameters
            - Control history
            - Current state
        """
        return {
            'config': self.config.__dict__,
            'history': self._history,
            'latest': self._history[-1] if self._history else None
        }


class TurbidostatProtocol(GrowthControlProtocol):
    """Turbidostat growth control protocol.
    
    Maintains constant cell density by diluting when OD exceeds threshold.
    No drug concentration adjustment.
    """
    # TODO: Implement turbidostat logic
    pass


class ChemostatProtocol(GrowthControlProtocol):
    """Chemostat growth control protocol.
    
    Maintains constant dilution rate regardless of growth.
    """
    # TODO: Implement chemostat logic
    pass 