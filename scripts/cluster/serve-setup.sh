#!/bin/bash
#
# Serve the worker setup script via HTTP
#
# Run this on the HEAD NODE to serve the setup script.
# Workers can then pull and run it.
#
# Usage:
#   ./scripts/cluster/serve-setup.sh
#
# Then on worker:
#   curl -sSL http://192.168.1.100:8080/setup-worker.sh | sudo bash -s -- --worker-id 1
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8080

echo "=============================================="
echo "  de_Funk Setup Server"
echo "=============================================="
echo ""
echo "  Serving from: $SCRIPT_DIR"
echo "  Port: $PORT"
echo ""
echo "  On each worker, run:"
echo ""
echo "    curl -sSL http://$(hostname -I | awk '{print $1}'):$PORT/setup-worker.sh | sudo bash -s -- --worker-id N"
echo ""
echo "  Replace N with worker number (1, 2, 3, etc.)"
echo ""
echo "  Press Ctrl+C to stop"
echo "=============================================="
echo ""

cd "$SCRIPT_DIR"
python3 -m http.server $PORT
