from flask import Flask, request
import logging
import sys

from replifactory_server.init import init_app, init_device

logger = logging.getLogger(__name__)

def create_app(config=None):
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Create Flask app
    app = Flask(__name__)
    
    # Add CORS preflight handler
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            response = app.make_default_options_response()
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
            response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
            return response
    
    # Initialize app components
    app = init_app(app, config)
    
    # Initialize device
    app = init_device(app)
    
    return app

def run_server(host='0.0.0.0', port=5000, mode='simulation', config=None):
    if config is None:
        config = {}
    config['MODE'] = mode
    
    app = create_app(config)
    logger.info(f"Starting server in {mode} mode on {host}:{port}")
    logger.info(f"Time acceleration factor: {app.config.get('TIME_ACCELERATION', 100.0)}x")
    
    socketio = app.config['socketio']
    socketio.run(app, host=host, port=port, debug=True, allow_unsafe_werkzeug=True)

def main():
    development = len(sys.argv) > 1 and sys.argv[1] == 'develop'
    
    config = {
        'MODE': 'simulation',  # Always use simulation mode
        'TIME_ACCELERATION': 100.0
    }
    
    if development:
        print("Running in development mode")
        app = create_app(config)
        app.run(debug=True, host="0.0.0.0", port=5000)
    else:
        print("Running in production mode")
        run_server(host="0.0.0.0", port=5000, mode='simulation', config=config)

if __name__ == '__main__':
    main()