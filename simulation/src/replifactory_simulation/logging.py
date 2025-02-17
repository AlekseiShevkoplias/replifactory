from dataclasses import dataclass, asdict
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Union
import pandas as pd
import numpy as np

@dataclass
class MeasurementLog:
    """Single measurement data point.
    
    Attributes:
        timestamp: Time of measurement
        vial: Vial number
        od: Optical density
        temperature: Temperature in Celsius
        drug_concentration: Current drug concentration
        growth_rate: Calculated growth rate if available
        action: Control action taken if any
    """
    timestamp: datetime
    vial: int
    od: float
    temperature: float
    drug_concentration: float
    growth_rate: Optional[float] = None
    action: Optional[str] = None

@dataclass
class ExperimentLog:
    """Complete experiment log.
    
    Attributes:
        experiment_id: Unique experiment identifier
        start_time: Experiment start time
        config: Experiment configuration
        measurements: List of all measurements
        events: List of significant events
    """
    experiment_id: str
    start_time: datetime
    config: Dict
    measurements: List[MeasurementLog] = None
    events: List[Dict] = None
    
    def __post_init__(self):
        self.measurements = self.measurements or []
        self.events = self.events or []


class SimulationLogger:
    """Handles data logging for simulated experiments.
    
    Logs measurements, events, and configuration to both:
    - CSV files for easy analysis
    - JSON for complete state preservation
    
    Args:
        output_dir: Directory for log files
        experiment_id: Unique experiment identifier
    """
    
    def __init__(self, output_dir: Union[str, Path], experiment_id: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.experiment_id = experiment_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.experiment_dir = self.output_dir / self.experiment_id
        self.experiment_dir.mkdir(exist_ok=True)
        
        self.log = ExperimentLog(
            experiment_id=self.experiment_id,
            start_time=datetime.now(),
            config={}
        )
        
    def log_config(self, config: Dict):
        """Log experiment configuration."""
        self.log.config = config
        self._save_json()
        
    def log_measurement(
        self,
        vial: int,
        od: float,
        temperature: float,
        drug_concentration: float,
        growth_rate: Optional[float] = None,
        action: Optional[str] = None
    ):
        """Log single measurement."""
        measurement = MeasurementLog(
            timestamp=datetime.now(),
            vial=vial,
            od=od,
            temperature=temperature,
            drug_concentration=drug_concentration,
            growth_rate=growth_rate,
            action=action
        )
        self.log.measurements.append(measurement)
        self._append_csv(measurement)
        
    def log_event(self, event_type: str, details: Dict):
        """Log significant event."""
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            **details
        }
        self.log.events.append(event)
        self._save_json()
        
    def _append_csv(self, measurement: MeasurementLog):
        """Append measurement to CSV file."""
        csv_path = self.experiment_dir / 'measurements.csv'
        
        # Convert to dict for pandas
        data = asdict(measurement)
        data['timestamp'] = data['timestamp'].isoformat()
        
        # Create or append to CSV
        df = pd.DataFrame([data])
        if not csv_path.exists():
            df.to_csv(csv_path, index=False)
        else:
            df.to_csv(csv_path, mode='a', header=False, index=False)
            
    def _save_json(self):
        """Save complete log to JSON."""
        json_path = self.experiment_dir / 'experiment.json'
        
        # Convert to serializable format
        data = asdict(self.log)
        data['start_time'] = data['start_time'].isoformat()
        
        for m in data['measurements']:
            m['timestamp'] = m['timestamp'].isoformat()
            
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
            
    def load_measurements(self) -> pd.DataFrame:
        """Load measurements as pandas DataFrame."""
        csv_path = self.experiment_dir / 'measurements.csv'
        if not csv_path.exists():
            return pd.DataFrame()
            
        df = pd.read_csv(csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    def plot_growth_curves(self):
        """Plot OD and drug concentration over time."""
        import matplotlib.pyplot as plt
        
        df = self.load_measurements()
        if df.empty:
            return
            
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        
        # Plot OD
        for vial in df['vial'].unique():
            vial_data = df[df['vial'] == vial]
            ax1.plot(vial_data['timestamp'], vial_data['od'], 
                    label=f'Vial {vial}')
        ax1.set_ylabel('OD')
        ax1.set_yscale('log')
        ax1.legend()
        ax1.grid(True)
        
        # Plot drug concentration
        for vial in df['vial'].unique():
            vial_data = df[df['vial'] == vial]
            ax2.plot(vial_data['timestamp'], vial_data['drug_concentration'],
                    label=f'Vial {vial}')
        ax2.set_ylabel('Drug Concentration')
        ax2.set_xlabel('Time')
        ax2.grid(True)
        
        plt.tight_layout()
        plt.savefig(self.experiment_dir / 'growth_curves.png')
        plt.close() 