import argparse
import logging
from replifactory_server.server import run_server

def main():
    parser = argparse.ArgumentParser(description='Start the Replifactory server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    parser.add_argument('--mode', default='simulation', choices=['simulation', 'hardware'], 
                       help='Server mode (simulation or hardware)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--time-acceleration', type=float, default=100.0,
                       help='Time acceleration factor for simulation mode (default: 100.0)')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run server
    config = {
        'MODE': args.mode,
        'TIME_ACCELERATION': args.time_acceleration
    }
    run_server(host=args.host, port=args.port, mode=args.mode, config=config)

if __name__ == '__main__':
    main() 