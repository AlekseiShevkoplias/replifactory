from datetime import datetime, timedelta
import logging
from typing import Dict, Optional
from flask import current_app
from replifactory_core.interfaces import DeviceEventListener
from replifactory_server.database_models import ExperimentModel

logger = logging.getLogger(__name__)

class ExperimentMonitor(DeviceEventListener):
    """Monitor for experiment events and device status updates."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.last_check = datetime.now() - timedelta(minutes=5)
        self.active_experiment: Optional[ExperimentModel] = None
        self.vial_data: Dict[int, Dict] = {}
        
    def get_active_experiment(self):
        """Get the currently running experiment."""
        experiment = ExperimentModel.query.filter_by(status='running')\
            .order_by(ExperimentModel.created_at.desc())\
            .first()
        if experiment:
            self.active_experiment = experiment
            return True
        return False
            
    def print_status(self, measurements):
        """Print formatted status update and emit WebSocket events."""
        self.logger.info("="*50)
        self.logger.info(f"Status Update at {datetime.now().strftime('%H:%M:%S')}")
        self.logger.info(f"Experiment: {self.active_experiment.name}")
        self.logger.info("-"*50)
        
        # Group measurements by vial
        vial_updates = {}
        for m in measurements:
            if m.vial not in vial_updates:
                vial_updates[m.vial] = []
            vial_updates[m.vial].append(m)
        
        # Process and emit measurements for each vial
        for vial in sorted(vial_updates.keys()):
            latest = vial_updates[vial][-1]  # Get most recent measurement
            vial_data = {
                'vial': vial,
                'od': float(latest.od),  # Ensure numeric type
                'temperature': float(latest.temperature),
                'drug_concentration': float(latest.drug_concentration) if latest.drug_concentration is not None else 0.0,
                'growth_rate': float(latest.growth_rate) if latest.growth_rate is not None else 0.0,
                'timestamp': latest.timestamp.isoformat()
            }
            
            # Emit vial update via WebSocket
            socketio = current_app.config['socketio']
            self.logger.debug(f"Emitting vial update: {vial_data}")
            socketio.emit('vial_update', vial_data)
            
            self.logger.info(f"\nVial {vial}:")
            self.logger.info(f"  OD: {latest.od:.3f}")
            self.logger.info(f"  Temperature: {latest.temperature:.1f}°C")
            if latest.drug_concentration is not None:
                self.logger.info(f"  Drug Concentration: {latest.drug_concentration:.2f}")
            if latest.growth_rate is not None:
                self.logger.info(f"  Growth Rate: {latest.growth_rate:.3f}/hr")
            
            # Calculate changes since last measurement
            if len(vial_updates[vial]) > 1:
                previous = vial_updates[vial][-2]
                od_change = latest.od - previous.od
                time_diff = (latest.timestamp - previous.timestamp).total_seconds() / 3600
                if time_diff > 0:
                    self.logger.info(f"  OD Change: {od_change:.3f} ({od_change/time_diff:.3f}/hr)")
        
        self.logger.info("="*50)
        
    def on_pump_status_change(self, pump_id: int, active: bool) -> None:
        """Emit pump status update via WebSocket."""
        socketio = current_app.config['socketio']
        socketio.emit('pump_status', {
            'pump': pump_id,
            'active': active,
            'timestamp': datetime.now().isoformat()
        })
        
    def on_valve_status_change(self, valve_id: int, is_open: bool) -> None:
        """Emit valve status update via WebSocket."""
        socketio = current_app.config['socketio']
        socketio.emit('valve_status', {
            'valve': valve_id,
            'open': is_open,
            'timestamp': datetime.now().isoformat()
        })

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    monitor = ExperimentMonitor()
    monitor.run()

if __name__ == '__main__':
    main() 