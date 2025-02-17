from replifactory_server.server import create_app
from replifactory_server.database_models import db, ExperimentModel, MeasurementData
import time
from datetime import datetime, timedelta
import sys
import logging
from typing import Dict, Optional

class ExperimentMonitor:
    def __init__(self):
        self.app = create_app()
        self.socketio = self.app.config['socketio']
        self.logger = logging.getLogger(__name__)
        self.last_check = datetime.now() - timedelta(minutes=5)
        self.active_experiment: Optional[ExperimentModel] = None
        self.vial_data: Dict[int, Dict] = {}
        
    def get_active_experiment(self):
        """Get the currently running experiment."""
        with self.app.app_context():
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
            self.vial_data[vial] = {
                'vial': vial,
                'od': latest.od,
                'temperature': latest.temperature,
                'drug_concentration': latest.drug_concentration,
                'growth_rate': latest.growth_rate,
                'timestamp': latest.timestamp.isoformat()
            }
            
            # Emit vial update via WebSocket
            with self.app.app_context():
                self.socketio.emit('vial_update', self.vial_data[vial])
            
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
        
    def run(self):
        """Main monitoring loop."""
        self.logger.info("Starting experiment monitor...")
        self.logger.info("Waiting for active experiment...")
        
        while True:
            try:
                # Check for active experiment
                if not self.active_experiment and not self.get_active_experiment():
                    time.sleep(5)
                    continue
                
                # Get new measurements
                with self.app.app_context():
                    new_measurements = MeasurementData.query.filter(
                        MeasurementData.timestamp > self.last_check,
                        MeasurementData.experiment_id == self.active_experiment.id
                    ).order_by(MeasurementData.timestamp).all()
                    
                    if new_measurements:
                        self.print_status(new_measurements)
                        self.last_check = new_measurements[-1].timestamp
                        
                        # Check if experiment is still running
                        self.active_experiment = ExperimentModel.query.get(
                            self.active_experiment.id
                        )
                        if self.active_experiment.status != 'running':
                            self.logger.info(f"\nExperiment {self.active_experiment.name} "
                                  f"ended with status: {self.active_experiment.status}")
                            self.active_experiment = None
                            self.last_check = datetime.now() - timedelta(minutes=5)
                            self.logger.info("\nWaiting for new experiment...")
                    else:
                        self.logger.debug("No new measurements found")
                
                time.sleep(2)  # Check for updates every 2 seconds
                
            except KeyboardInterrupt:
                self.logger.info("\nStopping monitor...")
                break
            except Exception as e:
                self.logger.error(f"Error in monitor: {str(e)}")
                time.sleep(5)  # Wait before retrying

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    monitor = ExperimentMonitor()
    monitor.run()

if __name__ == '__main__':
    main() 