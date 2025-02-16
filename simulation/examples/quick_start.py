from replifactory_simulation.runner import SimulationRunner
from replifactory_core.experiment import ExperimentConfig
from replifactory_simulation.growth_model import GrowthModelParameters
import time
from datetime import datetime

def format_time(hours):
    """Format time in hours nicely"""
    return f"{int(hours)}h {int((hours % 1) * 60)}m"

def main():
    # Create a longer experiment configuration
    exp_config = ExperimentConfig(
        measurement_interval_mins=10,    # Measure every 10 minutes
        max_duration_hours=24           # Run for 24 hours
    )
    
    # Configure realistic growth parameters
    model_params = GrowthModelParameters(
        doubling_time_mins=30,          # Fast growing bacteria
        initial_od=0.1,                 # Starting OD
        carrying_capacity=1.0,          # Maximum OD
        ic50_initial=10.0              # Initial drug resistance
    )
    
    # Create simulation with 100x speed acceleration (24h will take ~14 min real time)
    runner = SimulationRunner(
        config=exp_config,
        model_params=model_params,
        time_acceleration=100.0
    )
    
    print(f"Starting simulation at {datetime.now().strftime('%H:%M:%S')}")
    print("Running 24-hour experiment at 100x speed")
    print("Press Ctrl+C to stop early\n")
    
    runner.start()
    
    try:
        last_print = time.time()
        while runner.experiment._status == "running":
            # Get current status
            status = runner.experiment.status
            current_time = status['duration_hours']
            
            # Print update every 5 seconds
            if time.time() - last_print >= 5.0:
                print(f"\nSimulation Time: {format_time(current_time)} / 24h")
                print("Culture Status:")
                for vial, data in status['cultures'].items():
                    print(f"  Vial {vial}:")
                    print(f"    OD: {data['od']:.3f}")
                    if 'drug_concentration' in data:
                        print(f"    Drug: {data['drug_concentration']:.1f}")
                    if 'growth_rate' in data:
                        print(f"    Growth Rate: {data['growth_rate']:.3f}/hr")
                last_print = time.time()
            
            # Don't burn CPU
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping simulation early...")
    finally:
        runner.stop()
        
        # Show results
        print("\nGenerating plots...")
        runner.logger.plot_growth_curves()
        print(f"\nResults saved in: simulation_logs/{runner.logger.experiment_id}/")
        
        # Load and show final statistics
        df = runner.logger.load_measurements()
        if not df.empty:
            print("\nExperiment Summary:")
            print(f"Duration: {format_time(df['timestamp'].max().hour)}")
            print(f"Total measurements: {len(df)}")
            print("\nFinal ODs:")
            final_ods = df.groupby('vial').last()['od']
            print(final_ods)
        else:
            print("\nNo measurements recorded!")

if __name__ == "__main__":
    main() 