#!/bin/bash
#
# Diagnose Spark Cluster Issues
#
# Run this on the head node to check why workers aren't connecting.
#
# Usage:
#   ./diagnose-cluster.sh
#

set -e

HEAD_IP="192.168.1.212"
DE_FUNK_USER="ms_trixie"
SPARK_MASTER_PORT=7077
SPARK_UI_PORT=8080

WORKERS=(
    "bark-1:192.168.1.207"
    "bark-2:192.168.1.202"
    "bark-3:192.168.1.203"
)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

section() {
    echo ""
    echo "======================================================================"
    echo "  $1"
    echo "======================================================================"
    echo ""
}

# =============================================================================
# Check Spark Master
# =============================================================================

section "Spark Master Status"

echo "Checking if Spark Master is running..."
if pgrep -f "org.apache.spark.deploy.master.Master" > /dev/null; then
    echo -e "${GREEN}✓ Spark Master process is running${NC}"
    pgrep -af "org.apache.spark.deploy.master.Master" | head -1
else
    echo -e "${RED}✗ Spark Master is NOT running${NC}"
    echo ""
    echo "Start it with:"
    echo "  ./scripts/cluster/init-cluster.sh"
    echo ""
    echo "Or manually:"
    echo "  source ~/venv/bin/activate"
    echo "  JAVA_HOME=\$(dirname \$(dirname \$(readlink -f \$(which java))))"
    echo "  SPARK_HOME=\$(python -c 'import pyspark; print(pyspark.__path__[0])')"
    echo "  nohup \$JAVA_HOME/bin/java -cp \"\$SPARK_HOME/jars/*\" org.apache.spark.deploy.master.Master --host $HEAD_IP --port $SPARK_MASTER_PORT > /tmp/spark-master.log 2>&1 &"
    exit 1
fi

echo ""
echo "Checking Spark Master Web UI..."
if curl -s "http://$HEAD_IP:$SPARK_UI_PORT" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Web UI is accessible at http://$HEAD_IP:$SPARK_UI_PORT${NC}"
else
    echo -e "${RED}✗ Web UI is NOT accessible${NC}"
fi

# =============================================================================
# Check Master Port Accessibility
# =============================================================================

section "Master Port Accessibility"

echo "Checking if port $SPARK_MASTER_PORT is listening..."
if netstat -tlnp 2>/dev/null | grep -q ":$SPARK_MASTER_PORT" || ss -tlnp 2>/dev/null | grep -q ":$SPARK_MASTER_PORT"; then
    echo -e "${GREEN}✓ Port $SPARK_MASTER_PORT is listening${NC}"
else
    echo -e "${RED}✗ Port $SPARK_MASTER_PORT is NOT listening${NC}"
fi

echo ""
echo "Checking firewall status..."
if command -v ufw &> /dev/null; then
    sudo ufw status 2>/dev/null || echo "  (Could not check UFW status)"
else
    echo "  UFW not installed"
fi

# =============================================================================
# Check Each Worker
# =============================================================================

section "Worker Status"

for w in "${WORKERS[@]}"; do
    IFS=':' read -r name ip <<< "$w"
    echo "--- $name ($ip) ---"
    echo ""

    # Check SSH
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$DE_FUNK_USER@$ip" "echo ok" &>/dev/null; then
        echo -e "${RED}✗ Cannot SSH to $name${NC}"
        echo ""
        continue
    fi
    echo -e "${GREEN}✓ SSH connection OK${NC}"

    # Check if service exists
    SERVICE_EXISTS=$(ssh -o ConnectTimeout=5 "$DE_FUNK_USER@$ip" "systemctl list-unit-files | grep -c spark-worker || echo 0" 2>/dev/null)
    if [ "$SERVICE_EXISTS" = "0" ]; then
        echo -e "${RED}✗ spark-worker service does not exist${NC}"
        echo "  The worker setup may have failed. Re-run init-cluster.sh"
        echo ""
        continue
    fi
    echo -e "${GREEN}✓ spark-worker service exists${NC}"

    # Check service status
    echo ""
    echo "Service status:"
    ssh -o ConnectTimeout=5 "$DE_FUNK_USER@$ip" "systemctl status spark-worker 2>&1 | head -10" || true

    # Check service file
    echo ""
    echo "Service file ExecStart:"
    ssh -o ConnectTimeout=5 "$DE_FUNK_USER@$ip" "grep ExecStart /etc/systemd/system/spark-worker.service" || true

    # Check recent logs
    echo ""
    echo "Recent logs (last 20 lines):"
    ssh -o ConnectTimeout=5 "$DE_FUNK_USER@$ip" "sudo journalctl -u spark-worker --no-pager -n 20" 2>/dev/null || true

    # Check if can reach master
    echo ""
    echo "Testing connection to master ($HEAD_IP:$SPARK_MASTER_PORT):"
    ssh -o ConnectTimeout=5 "$DE_FUNK_USER@$ip" "nc -zv $HEAD_IP $SPARK_MASTER_PORT 2>&1 || echo 'nc not installed, trying curl...' && curl -s --connect-timeout 2 http://$HEAD_IP:$SPARK_UI_PORT > /dev/null && echo 'Can reach master UI'" 2>/dev/null || echo "  Could not test connectivity"

    echo ""
done

# =============================================================================
# Summary
# =============================================================================

section "Cluster Summary"

echo "Querying Spark Master API..."
CLUSTER_INFO=$(curl -s "http://$HEAD_IP:$SPARK_UI_PORT/json/" 2>/dev/null || echo "{}")

if [ -n "$CLUSTER_INFO" ] && [ "$CLUSTER_INFO" != "{}" ]; then
    echo "$CLUSTER_INFO" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    workers = data.get('workers', [])
    print(f'Status: {data.get(\"status\", \"unknown\")}')
    print(f'Workers connected: {len(workers)}')
    for w in workers:
        print(f'  - {w.get(\"host\")}:{w.get(\"port\")} - {w.get(\"cores\")} cores, {w.get(\"memory\")/1024:.1f}GB')
    print(f'Total cores: {data.get(\"cores\", 0)} (used: {data.get(\"coresused\", 0)})')
    print(f'Total memory: {data.get(\"memory\", 0)}MB (used: {data.get(\"memoryused\", 0)}MB)')
except Exception as e:
    print(f'Error parsing: {e}')
" 2>/dev/null || echo "  Could not parse cluster info"
else
    echo -e "${RED}Could not get cluster info from master${NC}"
fi

echo ""
echo "======================================================================"
echo "  Next Steps"
echo "======================================================================"
echo ""
echo "If workers aren't connecting:"
echo "  1. Check the service file has correct paths (no unresolved variables)"
echo "  2. Check journalctl logs for startup errors"
echo "  3. Verify workers can reach master on port $SPARK_MASTER_PORT"
echo "  4. Try restarting workers: ssh bark-1 'sudo systemctl restart spark-worker'"
echo ""
