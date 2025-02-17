from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import sys

def run(port=8000):
    """Run the HTTP server on the specified port."""
    server_address = ('', port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print(f"Starting UI server on port {port}")
    print(f"Open http://localhost:{port} in your browser")
    httpd.serve_forever()

if __name__ == '__main__':
    # Change to the directory containing this script
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Get port from command line argument or use default
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run(port) 