from replifactory_simulation.runner import SimulationRunner
from replifactory_core.experiment import ExperimentConfig
from replifactory_simulation.growth_model import GrowthModelParameters
import time
import logging
from datetime import datetime

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Create configuration
    exp_config = ExperimentConfig(
        measurement_interval_mins=10,
        max_duration_hours=24,
        max_generations=None  # Allow experiment to run full duration
    )
    
    # Configure realistic growth parameters
    model_params = GrowthModelParameters(
        doubling_time_mins=30,        # Fast growing bacteria
        initial_od=0.1,               # Starting OD
        carrying_capacity=1.0,        # Maximum OD
        ic50_initial=10.0,            # Initial drug resistance
        adaptation_rate_max=0.1       # Allow for evolution
    )
    
    print(f"Starting simulation at {datetime.now().strftime('%H:%M:%S')}")
    print(f"Running {exp_config.max_duration_hours}-hour experiment at 10000x speed")
    print("Press Ctrl+C to stop early\n")
    
    # Create simulation
    runner = SimulationRunner(
        config=exp_config,
        model_params=model_params,
        time_acceleration=10000.0
    )
    
    try:
        # Start simulation
        runner.start()
        
        # Monitor progress
        start_time = time.time()
        last_print = start_time
        
        while runner.experiment._status == "running":
            current_time = time.time()
            
            # Print status update every 5 seconds
            if current_time - last_print >= 5.0:
                status = runner.experiment.status
                sim_hours = status['duration_hours']
                
                print(f"\nSimulation Time: {sim_hours:.1f}h / {exp_config.max_duration_hours}h")
                print("Culture Status:")
                
                for vial, data in status['cultures'].items():
                    print(f"  Vial {vial}:")
                    print(f"    OD: {data['od']:.3f}")
                    if 'drug_concentration' in data:
                        print(f"    Drug: {data['drug_concentration']:.1f}")
                    if 'growth_rate' in data:
                        print(f"    Growth Rate: {data['growth_rate']:.3f}/hr")
                        
                last_print = current_time
            
            # Don't burn CPU
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping simulation early...")
    finally:
        runner.stop()
        
        # Show results
        print("\nGenerating plots...")
        runner.data_logger.plot_growth_curves()
        
        # Load and show final statistics
        df = runner.data_logger.load_measurements()
        if not df.empty:
            print("\nExperiment Summary:")
            print(f"Duration: {df['timestamp'].max() - df['timestamp'].min()}")
            print(f"Total measurements: {len(df)}")
            print("\nFinal ODs:")
            final_ods = df.groupby('vial').last()['od']
            print(final_ods)
        else:
            logger.warning("No measurements recorded!")

if __name__ == "__main__":
    main()