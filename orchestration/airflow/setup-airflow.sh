#!/bin/bash
#
# Airflow Setup Script (Head Node)
#
# Installs and configures Apache Airflow for de_Funk orchestration.
# Run this on the head node (bigbark) after Spark cluster is set up.
#
# Usage:
#   ./setup-airflow.sh
#   ./setup-airflow.sh --with-systemd   # Install as system service
#
# Prerequisites:
#   - Python 3.11+ with venv
#   - Spark cluster running (optional, but needed for Silver builds)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# Configuration
# =============================================================================

DE_FUNK_USER="${DE_FUNK_USER:-ms_trixie}"
SPARK_VENV_PATH="${VENV_PATH:-/home/$DE_FUNK_USER/venv}"
PROJECT_ROOT="${PROJECT_ROOT:-/shared/de_Funk}"
AIRFLOW_HOME="${AIRFLOW_HOME:-/home/$DE_FUNK_USER/airflow}"

# Airflow needs its own venv (Python 3.12 max, main venv may be 3.13)
AIRFLOW_VENV_PATH="/home/$DE_FUNK_USER/airflow-venv"

# Airflow config - use latest 3.x that supports Python 3.12
AIRFLOW_PORT=8081  # 8080 is used by Spark Master UI
AIRFLOW_VERSION="3.0.4"
PYTHON_VERSION="3.12"

# Find Python 3.12 (required for Airflow)
PYTHON_BIN=""
for py in python3.12 python3.11; do
    if command -v $py &> /dev/null; then
        PYTHON_BIN=$(command -v $py)
        PYTHON_VERSION=$(echo $py | sed 's/python//')
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: Python 3.11 or 3.12 required for Airflow (found Python 3.13+ only)"
    echo "Install with: sudo apt install python3.12 python3.12-venv"
    exit 1
fi

WITH_SYSTEMD=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --with-systemd)
            WITH_SYSTEMD=true
            shift
            ;;
        --airflow-home)
            AIRFLOW_HOME="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --with-systemd     Install as systemd service"
            echo "  --airflow-home     Airflow home directory (default: ~/airflow)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "======================================================================"
echo "  Airflow Setup for de_Funk"
echo "======================================================================"
echo ""
echo "User: $DE_FUNK_USER"
echo "Python: $PYTHON_BIN (v$PYTHON_VERSION)"
echo "Airflow Venv: $AIRFLOW_VENV_PATH"
echo "Airflow Home: $AIRFLOW_HOME"
echo "Airflow Version: $AIRFLOW_VERSION"
echo "Project Root: $PROJECT_ROOT"
echo "Install systemd: $WITH_SYSTEMD"
echo ""

# =============================================================================
# Install Airflow
# =============================================================================

echo "----------------------------------------------------------------------"
echo "Step 1: Creating Airflow Python Environment"
echo "----------------------------------------------------------------------"

# Create separate venv for Airflow (uses Python 3.12, not 3.13)
if [ ! -d "$AIRFLOW_VENV_PATH" ]; then
    echo "  Creating venv with $PYTHON_BIN..."
    $PYTHON_BIN -m venv "$AIRFLOW_VENV_PATH"
fi

source "$AIRFLOW_VENV_PATH/bin/activate"

echo "  ✓ Airflow venv activated"

echo ""
echo "----------------------------------------------------------------------"
echo "Step 2: Installing Apache Airflow"
echo "----------------------------------------------------------------------"

pip install --upgrade pip setuptools wheel -q

# Install Airflow with constraints (recommended way)
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

echo "  Installing Airflow ${AIRFLOW_VERSION} with constraints..."
pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT_URL}"
pip install apache-airflow-providers-apache-spark

echo "  ✓ Airflow installed"

# =============================================================================
# Initialize Airflow
# =============================================================================

echo ""
echo "----------------------------------------------------------------------"
echo "Step 3: Initializing Airflow"
echo "----------------------------------------------------------------------"

export AIRFLOW_HOME="$AIRFLOW_HOME"
mkdir -p "$AIRFLOW_HOME/dags" "$AIRFLOW_HOME/logs" "$AIRFLOW_HOME/plugins"

# Initialize database (Airflow 3.x uses 'migrate' instead of 'init')
airflow db migrate

echo "  ✓ Airflow database initialized"

# =============================================================================
# Configure Airflow
# =============================================================================

echo ""
echo "----------------------------------------------------------------------"
echo "Step 4: Configuring Airflow"
echo "----------------------------------------------------------------------"

# Update airflow.cfg for local development
AIRFLOW_CFG="$AIRFLOW_HOME/airflow.cfg"

# Set executor (LocalExecutor for single-node, CeleryExecutor for distributed)
sed -i 's/^executor = .*/executor = LocalExecutor/' "$AIRFLOW_CFG"

# Disable example DAGs
sed -i 's/^load_examples = .*/load_examples = False/' "$AIRFLOW_CFG"

# Set web server port
sed -i "s/^web_server_port = .*/web_server_port = $AIRFLOW_PORT/" "$AIRFLOW_CFG"

# Set timezone
sed -i 's/^default_timezone = .*/default_timezone = UTC/' "$AIRFLOW_CFG"

# Increase parallelism for Spark jobs
sed -i 's/^parallelism = .*/parallelism = 8/' "$AIRFLOW_CFG"
sed -i 's/^max_active_tasks_per_dag = .*/max_active_tasks_per_dag = 4/' "$AIRFLOW_CFG"

echo "  ✓ Airflow configured"

# =============================================================================
# Create Admin User
# =============================================================================

echo ""
echo "----------------------------------------------------------------------"
echo "Step 5: Creating Admin User"
echo "----------------------------------------------------------------------"

airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@defunk.local \
    --password admin123 \
    2>/dev/null || echo "  (User may already exist)"

echo "  ✓ Admin user created (admin / admin123)"

# =============================================================================
# Copy DAGs
# =============================================================================

echo ""
echo "----------------------------------------------------------------------"
echo "Step 6: Installing DAGs"
echo "----------------------------------------------------------------------"

# Copy de_funk DAG
cp "$PROJECT_ROOT/orchestration/airflow/dags/"*.py "$AIRFLOW_HOME/dags/"

echo "  ✓ DAGs copied to $AIRFLOW_HOME/dags/"

# List DAGs
ls -la "$AIRFLOW_HOME/dags/"

# =============================================================================
# Configure Spark Connection
# =============================================================================

echo ""
echo "----------------------------------------------------------------------"
echo "Step 7: Configuring Spark Connection"
echo "----------------------------------------------------------------------"

# Add Spark connection via CLI
airflow connections add 'spark_default' \
    --conn-type 'spark' \
    --conn-host 'spark://192.168.1.212' \
    --conn-port '7077' \
    2>/dev/null || echo "  (Connection may already exist)"

echo "  ✓ Spark connection configured"

# =============================================================================
# Systemd Service (Optional)
# =============================================================================

if [ "$WITH_SYSTEMD" = true ]; then
    echo ""
    echo "----------------------------------------------------------------------"
    echo "Step 8: Installing Systemd Services"
    echo "----------------------------------------------------------------------"

    # Airflow Webserver Service
    sudo tee /etc/systemd/system/airflow-webserver.service > /dev/null <<EOF
[Unit]
Description=Airflow Webserver
After=network.target

[Service]
Type=simple
User=$DE_FUNK_USER
Environment="AIRFLOW_HOME=$AIRFLOW_HOME"
Environment="PATH=$AIRFLOW_VENV_PATH/bin:/usr/local/bin:/usr/bin"
ExecStart=$AIRFLOW_VENV_PATH/bin/airflow webserver --port $AIRFLOW_PORT
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Airflow Scheduler Service
    sudo tee /etc/systemd/system/airflow-scheduler.service > /dev/null <<EOF
[Unit]
Description=Airflow Scheduler
After=network.target

[Service]
Type=simple
User=$DE_FUNK_USER
Environment="AIRFLOW_HOME=$AIRFLOW_HOME"
Environment="PATH=$AIRFLOW_VENV_PATH/bin:/usr/local/bin:/usr/bin"
ExecStart=$AIRFLOW_VENV_PATH/bin/airflow scheduler
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable airflow-webserver airflow-scheduler

    echo "  ✓ Systemd services installed"
    echo ""
    echo "  Start with:"
    echo "    sudo systemctl start airflow-webserver"
    echo "    sudo systemctl start airflow-scheduler"
fi

# =============================================================================
# Create Start/Stop Scripts
# =============================================================================

echo ""
echo "----------------------------------------------------------------------"
echo "Step 9: Creating Management Scripts"
echo "----------------------------------------------------------------------"

# Start script
cat > "$AIRFLOW_HOME/start-airflow.sh" <<EOF
#!/bin/bash
export AIRFLOW_HOME="$AIRFLOW_HOME"
source "$AIRFLOW_VENV_PATH/bin/activate"

echo "Starting Airflow..."

# Start scheduler in background
airflow scheduler &
SCHEDULER_PID=\$!
echo \$SCHEDULER_PID > "$AIRFLOW_HOME/scheduler.pid"

# Start webserver in background
airflow webserver --port $AIRFLOW_PORT &
WEBSERVER_PID=\$!
echo \$WEBSERVER_PID > "$AIRFLOW_HOME/webserver.pid"

echo ""
echo "Airflow started!"
echo "  Scheduler PID: \$SCHEDULER_PID"
echo "  Webserver PID: \$WEBSERVER_PID"
echo "  Web UI: http://\$(hostname -I | awk '{print \$1}'):$AIRFLOW_PORT"
echo ""
echo "Stop with: $AIRFLOW_HOME/stop-airflow.sh"
EOF
chmod +x "$AIRFLOW_HOME/start-airflow.sh"

# Stop script
cat > "$AIRFLOW_HOME/stop-airflow.sh" <<EOF
#!/bin/bash
echo "Stopping Airflow..."

if [ -f "$AIRFLOW_HOME/scheduler.pid" ]; then
    kill \$(cat "$AIRFLOW_HOME/scheduler.pid") 2>/dev/null
    rm "$AIRFLOW_HOME/scheduler.pid"
fi

if [ -f "$AIRFLOW_HOME/webserver.pid" ]; then
    kill \$(cat "$AIRFLOW_HOME/webserver.pid") 2>/dev/null
    rm "$AIRFLOW_HOME/webserver.pid"
fi

# Kill any remaining
pkill -f "airflow scheduler" 2>/dev/null
pkill -f "airflow webserver" 2>/dev/null

echo "  ✓ Airflow stopped"
EOF
chmod +x "$AIRFLOW_HOME/stop-airflow.sh"

echo "  ✓ Management scripts created"

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "======================================================================"
echo "  Airflow Setup Complete!"
echo "======================================================================"
echo ""
echo "Quick Start:"
echo "  1. Start Airflow:  $AIRFLOW_HOME/start-airflow.sh"
echo "  2. Open Web UI:    http://$(hostname -I | awk '{print $1}'):$AIRFLOW_PORT"
echo "  3. Login:          admin / admin123"
echo "  4. Enable DAG:     Toggle 'de_funk_pipeline' ON"
echo ""
echo "Management:"
echo "  Start:   $AIRFLOW_HOME/start-airflow.sh"
echo "  Stop:    $AIRFLOW_HOME/stop-airflow.sh"
echo "  Logs:    tail -f $AIRFLOW_HOME/logs/scheduler/latest/*.log"
echo ""
echo "Manual trigger:"
echo "  airflow dags trigger de_funk_pipeline"
echo ""
if [ "$WITH_SYSTEMD" = true ]; then
echo "Systemd:"
echo "  sudo systemctl start airflow-webserver airflow-scheduler"
echo "  sudo systemctl status airflow-webserver"
echo ""
fi
