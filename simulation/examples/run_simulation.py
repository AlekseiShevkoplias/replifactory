from replifactory_simulation.runner import SimulationRunner
from replifactory_core.experiment import ExperimentConfig
from replifactory_simulation.growth_model import GrowthModelParameters
import time
import logging

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create configuration
    exp_config = ExperimentConfig(
        measurement_interval_mins=10,
        max_duration_hours=24
    )
    
    model_params = GrowthModelParameters(
        doubling_time_mins=30,
        initial_od=0.1,
        carrying_capacity=1.0,
        ic50_initial=10.0
    )
    
    # Create and start simulation
    runner = SimulationRunner(
        config=exp_config,
        model_params=model_params,
        time_acceleration=100.0  # 100x speed
    )
    
    try:
        runner.start()
        
        # Monitor simulation
        while runner.experiment._status == "running":
            status = runner.experiment.status
            logging.info(f"Time: {status['duration_hours']:.1f}h")
            
            # Print culture status every minute
            for vial, data in status['cultures'].items():
                logging.info(
                    f"Vial {vial}: OD={data['od']:.3f}, "
                    f"Drug={data.get('drug_concentration', 0.0):.1f}"
                )
            
            time.sleep(60)  # Update display every minute
            
    except KeyboardInterrupt:
        logging.info("Stopping simulation...")
    finally:
        runner.stop()
        
        # Generate final plots and summary
        runner.data_logger.plot_growth_curves()
        
        df = runner.data_logger.load_measurements()
        if not df.empty:
            logging.info("\nExperiment Summary:")
            duration = df['timestamp'].max() - df['timestamp'].min()
            logging.info(f"Duration: {duration}")
            logging.info(f"Total measurements: {len(df)}")
            logging.info("\nFinal ODs:")
            final_ods = df.groupby('vial').last()['od']
            logging.info(final_ods)
        else:
            logging.warning("No measurements recorded!")

if __name__ == "__main__":
    main()