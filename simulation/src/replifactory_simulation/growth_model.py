from dataclasses import dataclass
import numpy as np
from typing import Optional


@dataclass
class GrowthModelParameters:
    """Parameters controlling bacterial growth simulation.
    
    Attributes:
        initial_od: Starting optical density
        doubling_time_mins: Time for population to double without drug
        carrying_capacity: Maximum OD the culture can reach
        mu_min: Minimum growth rate (can be negative for death)
        ic50_initial: Initial drug concentration causing 50% growth inhibition
        ic10_ic50_ratio: Ratio of IC10 to IC50 (controls dose response curve)
        adaptation_rate_max: Maximum rate of drug adaptation
        adaptation_rate_ic10_ic50_ratio: Controls adaptation vs. drug concentration
    """
    initial_od: float = 0.05
    doubling_time_mins: float = 20.0
    carrying_capacity: float = 0.9
    mu_min: float = -0.1
    ic50_initial: float = 5.0
    ic10_ic50_ratio: float = 0.5
    adaptation_rate_max: float = 0.08
    adaptation_rate_ic10_ic50_ratio: float = 0.8


class GrowthModel:
    """Simulates bacterial growth with drug adaptation.
    
    Implements core growth model including:
    - Basic bacterial growth
    - Drug response
    - Evolution of drug resistance
    - Population carrying capacity
    
    The model tracks:
    - Current population (OD)
    - Drug concentration
    - Drug resistance (IC50)
    - Growth rate
    """
    
    def __init__(self, parameters: Optional[GrowthModelParameters] = None):
        """Initialize growth model.
        
        Args:
            parameters: Growth model parameters. Uses defaults if None.
        """
        self.params = parameters or GrowthModelParameters()
        
        # Calculate base growth rate from doubling time
        self.mu_max = np.log(2) / (self.params.doubling_time_mins / 60)
        
        # Initialize state
        self.od = self.params.initial_od
        self.drug_concentration = 0.0
        self.ic50 = self.params.ic50_initial
        self._growth_rate = None
        
    def growth_rate(self, drug_conc: float, od: float) -> float:
        """Calculate growth rate under given conditions.
        
        Combines effects of:
        - Base growth rate
        - Drug inhibition
        - Carrying capacity
        
        Args:
            drug_conc: Current drug concentration
            od: Current optical density
            
        Returns:
            Growth rate in 1/hour
        """
        # Calculate drug effect using 4-parameter logistic
        ic10 = self.ic50 * self.params.ic10_ic50_ratio
        k = np.log(9) / (self.ic50 - ic10)
        drug_effect = self.params.mu_min + (
            self.mu_max / (1 + np.exp(-k * (self.ic50 - drug_conc)))
        )
        
        # Apply carrying capacity limitation
        capacity_effect = (1 - od / self.params.carrying_capacity)
        
        return drug_effect * capacity_effect
    
    def adaptation_rate(self, drug_conc: float) -> float:
        """Calculate rate of drug resistance adaptation.
        
        Models evolution of drug resistance using modified Gaussian curve.
        
        Args:
            drug_conc: Current drug concentration
            
        Returns:
            Adaptation rate in 1/hour
        """
        ic10 = self.ic50 * self.params.ic10_ic50_ratio
        k_adapt = -np.log(self.params.adaptation_rate_ic10_ic50_ratio) / ((ic10 - self.ic50) ** 2)
        return self.params.adaptation_rate_max * np.exp(-k_adapt * ((drug_conc - self.ic50) ** 2))
    
    def update(self, timestep_mins: float, new_drug_conc: Optional[float] = None):
        """Update model state for one timestep.
        
        Args:
            timestep_mins: Time step in minutes
            new_drug_conc: New drug concentration if changed, else uses current
            
        Updates internal state:
        - OD based on growth
        - IC50 based on adaptation
        - Stores current growth rate
        """
        if new_drug_conc is not None:
            self.drug_concentration = new_drug_conc
            
        # Calculate current growth rate
        self._growth_rate = self.growth_rate(self.drug_concentration, self.od)
        
        # Update population
        hours = timestep_mins / 60
        self.od *= np.exp(self._growth_rate * hours)
        
        # Update drug resistance
        adapt_rate = self.adaptation_rate(self.drug_concentration)
        self.ic50 *= np.exp(adapt_rate * hours)
    
    def dilute(self, dilution_factor: float, new_drug_conc: Optional[float] = None):
        """Perform dilution operation.
        
        Args:
            dilution_factor: Factor by which culture is diluted
            new_drug_conc: New drug concentration after dilution
        """
        self.od /= dilution_factor
        if new_drug_conc is not None:
            self.drug_concentration = new_drug_conc
            
    @property
    def growth_rate_current(self) -> float:
        """Get most recently calculated growth rate."""
        return self._growth_rate if self._growth_rate is not None else 0.0