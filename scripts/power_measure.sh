#!/bin/bash
# QXChain Power Measurement - Comprehensive blockchain function testing
# Creates timestamped folder with data and graphs

RAPL_PKG="/sys/class/powercap/intel-rapl:0/energy_uj"
RAPL_CORE="/sys/class/powercap/intel-rapl:0:0/energy_uj"
BASE_DIR="/home/teo/qxchain/power_results"
RPC_URL="http://127.0.0.1:9944"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create timestamped folder with data and graphs subfolders
RUN_DIR="$BASE_DIR/runs/$TIMESTAMP"
DATA_DIR="$RUN_DIR/data"
GRAPHS_DIR="$RUN_DIR/graphs"
mkdir -p "$DATA_DIR" "$GRAPHS_DIR"

SAMPLE_INTERVAL=0.1
SAMPLES=100

# Alice's address for queries
ALICE="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
BOB="5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"

get_block() {
    local r=$(curl -s -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"chain_getHeader","params":[]}' "$RPC_URL" 2>/dev/null)
    local h=$(echo "$r" | grep -o '"number":"[^"]*"' | cut -d'"' -f4)
    echo $((16#${h#0x}))
}

get_finalized() {
    local hash=$(curl -s -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"chain_getFinalizedHead","params":[]}' "$RPC_URL" 2>/dev/null | grep -o '"result":"[^"]*"' | cut -d'"' -f4)
    local r=$(curl -s -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"chain_getHeader\",\"params\":[\"$hash\"]}" "$RPC_URL" 2>/dev/null)
    local h=$(echo "$r" | grep -o '"number":"[^"]*"' | cut -d'"' -f4)
    echo $((16#${h#0x}))
}

measure() {
    local name="$1"
    local samples="$2"
    local file="$DATA_DIR/${name}.csv"

    echo "timestamp_ns,elapsed_ms,block,finalized,pkg_uj,core_uj,delta_pkg_uj,delta_core_uj,pkg_mw,core_mw" > "$file"

    local prev_pkg=$(cat "$RAPL_PKG")
    local prev_core=$(cat "$RAPL_CORE")
    local start=$(date +%s%N)
    local prev_t=$start

    for ((i=1; i<=samples; i++)); do
        sleep $SAMPLE_INTERVAL
        local now=$(date +%s%N)
        local pkg=$(cat "$RAPL_PKG")
        local core=$(cat "$RAPL_CORE")
        local blk=$(get_block)
        local fin=$(get_finalized)
        local elapsed=$(( (now - start) / 1000000 ))
        local dt=$(( (now - prev_t) / 1000 ))
        local dp=$((pkg - prev_pkg))
        local dc=$((core - prev_core))
        local pw=0 cw=0
        [ $dt -gt 0 ] && pw=$(( (dp * 1000) / dt )) && cw=$(( (dc * 1000) / dt ))
        echo "$now,$elapsed,$blk,$fin,$pkg,$core,$dp,$dc,$pw,$cw" >> "$file"
        prev_pkg=$pkg; prev_core=$core; prev_t=$now
    done
    echo "  -> $file ($samples samples)"
}

echo "=== QXChain Power Measurement ==="
echo "Timestamp: $TIMESTAMP"
echo "Run dir: $RUN_DIR"
echo ""

# ==============================================================================
# BASELINE TESTS
# ==============================================================================

# 1. IDLE - System baseline (chain running, minimal activity between blocks)
echo "[01/16] idle_baseline..."
measure "idle_baseline" $SAMPLES

# 2. IDLE - Chain running, no external load
echo "[02/16] idle_consensus_running..."
measure "idle_consensus_running" $SAMPLES

# ==============================================================================
# CONSENSUS TESTS
# ==============================================================================

# 3. BLOCK_PRODUCTION - AURA authoring new blocks
echo "[03/16] block_production_aura..."
measure "block_production_aura" $SAMPLES

# 4. FINALIZATION - GRANDPA finalizing blocks
echo "[04/16] finalization_grandpa..."
measure "finalization_grandpa" $SAMPLES

# ==============================================================================
# TRANSACTION POOL TESTS
# ==============================================================================

# 5. PENDING_EXTRINSICS - Query transaction pool
echo "[05/16] tx_pool_pending..."
(
while true; do
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"author_pendingExtrinsics","params":[]}' \
        "$RPC_URL" > /dev/null 2>&1
    sleep 0.02
done
) &
BG_PID=$!
measure "tx_pool_pending" $SAMPLES
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null

# ==============================================================================
# BALANCE & ACCOUNT TESTS
# ==============================================================================

# 6. ACCOUNT_INFO - Query account information
echo "[06/16] account_info_query..."
(
while true; do
    # Query Alice's account info (System.Account storage)
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"state_call","params":["AccountNonceApi_account_nonce","0xd43593c715fdd31c61141abd04a99fd6822c8558854ccde39a5684e7a56da27d"]}' \
        "$RPC_URL" > /dev/null 2>&1
done
) &
BG_PID=$!
measure "account_info_query" $SAMPLES
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null

# 7. BALANCE_QUERY - Query account balances
echo "[07/16] balance_query..."
(
while true; do
    # Query balances storage for Alice
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"state_getStorage","params":["0x26aa394eea5630e07c48ae0c9558cef7b99d880ec681799c0cf30e8886371da9de1e86a9a8c739864cf3cc5ec2bea59fd43593c715fdd31c61141abd04a99fd6822c8558854ccde39a5684e7a56da27d"]}' \
        "$RPC_URL" > /dev/null 2>&1
    # Query for Bob too
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"state_getStorage","params":["0x26aa394eea5630e07c48ae0c9558cef7b99d880ec681799c0cf30e8886371da98ab0f98a61f8c48746387f784266c26f8eaf04151687736326c9fea17e25fc5287613693c912909cb226aa4794f26a48"]}' \
        "$RPC_URL" > /dev/null 2>&1
done
) &
BG_PID=$!
measure "balance_query" $SAMPLES
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null

# ==============================================================================
# STATE STORAGE TESTS
# ==============================================================================

# 8. STATE_READ_SIMPLE - Simple storage reads
echo "[08/16] state_read_simple..."
(
while true; do
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"state_getStorage","params":["0x"]}' \
        "$RPC_URL" > /dev/null 2>&1
done
) &
BG_PID=$!
measure "state_read_simple" $SAMPLES
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null

# 9. STATE_READ_KEYS - Query storage keys
echo "[09/16] state_read_keys..."
(
while true; do
    # Get storage keys for System pallet
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"state_getKeys","params":["0x26aa394eea5630e07c48ae0c9558cef7"]}' \
        "$RPC_URL" > /dev/null 2>&1
done
) &
BG_PID=$!
measure "state_read_keys" $SAMPLES
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null

# 10. STATE_READ_RUNTIME - Query runtime version
echo "[10/16] state_runtime_version..."
(
while true; do
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"state_getRuntimeVersion","params":[]}' \
        "$RPC_URL" > /dev/null 2>&1
done
) &
BG_PID=$!
measure "state_runtime_version" $SAMPLES
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null

# ==============================================================================
# CHAIN QUERY TESTS
# ==============================================================================

# 11. CHAIN_GET_BLOCK - Query full block data
echo "[11/16] chain_get_block..."
(
while true; do
    # Get latest block hash then full block
    hash=$(curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"chain_getBlockHash","params":[]}' \
        "$RPC_URL" | grep -o '"result":"[^"]*"' | cut -d'"' -f4)
    curl -s -H "Content-Type: application/json" \
        -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"chain_getBlock\",\"params\":[\"$hash\"]}" \
        "$RPC_URL" > /dev/null 2>&1
done
) &
BG_PID=$!
measure "chain_get_block" $SAMPLES
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null

# 12. CHAIN_GET_HEADER - Query block headers
echo "[12/16] chain_get_header..."
(
while true; do
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"chain_getHeader","params":[]}' \
        "$RPC_URL" > /dev/null 2>&1
done
) &
BG_PID=$!
measure "chain_get_header" $SAMPLES
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null

# ==============================================================================
# RPC TESTS
# ==============================================================================

# 13. RPC_METADATA - Heavy RPC call (full metadata)
echo "[13/16] rpc_metadata_fetch..."
(
while true; do
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"state_getMetadata","params":[]}' \
        "$RPC_URL" > /dev/null 2>&1
done
) &
BG_PID=$!
measure "rpc_metadata_fetch" $SAMPLES
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null

# 14. RPC_SYSTEM - System info queries
echo "[14/16] rpc_system_info..."
(
while true; do
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"system_health","params":[]}' \
        "$RPC_URL" > /dev/null 2>&1
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"system_peers","params":[]}' \
        "$RPC_URL" > /dev/null 2>&1
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"system_version","params":[]}' \
        "$RPC_URL" > /dev/null 2>&1
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"system_chain","params":[]}' \
        "$RPC_URL" > /dev/null 2>&1
done
) &
BG_PID=$!
measure "rpc_system_info" $SAMPLES
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null

# ==============================================================================
# RUNTIME API TESTS
# ==============================================================================

# 15. RUNTIME_CALL - Runtime API calls
echo "[15/16] runtime_api_calls..."
(
while true; do
    # Call Core_version
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"state_call","params":["Core_version",""]}' \
        "$RPC_URL" > /dev/null 2>&1
    # Call Metadata_metadata
    curl -s -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"state_call","params":["Metadata_metadata",""]}' \
        "$RPC_URL" > /dev/null 2>&1
done
) &
BG_PID=$!
measure "runtime_api_calls" $SAMPLES
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null

# 16. MIXED_WORKLOAD - Combined realistic workload
echo "[16/16] mixed_workload..."
(
while true; do
    # Simulate realistic usage pattern
    curl -s -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"chain_getHeader","params":[]}' "$RPC_URL" > /dev/null 2>&1
    curl -s -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"system_health","params":[]}' "$RPC_URL" > /dev/null 2>&1
    curl -s -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"state_getRuntimeVersion","params":[]}' "$RPC_URL" > /dev/null 2>&1
    curl -s -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"author_pendingExtrinsics","params":[]}' "$RPC_URL" > /dev/null 2>&1
    sleep 0.01
done
) &
BG_PID=$!
measure "mixed_workload" $SAMPLES
kill $BG_PID 2>/dev/null; wait $BG_PID 2>/dev/null

echo ""
echo "=== Data Collection Complete ==="

# Summary
echo "Summary (avg power in Watts):"
printf "%-25s %10s %10s\n" "Function" "Package" "Core"
printf "%-25s %10s %10s\n" "--------" "-------" "----"
for f in "$DATA_DIR"/*.csv; do
    name=$(basename "$f" .csv)
    pkg_avg=$(awk -F',' 'NR>1 {sum+=$9; n++} END {printf "%.1f", sum/n/1000}' "$f")
    core_avg=$(awk -F',' 'NR>1 {sum+=$10; n++} END {printf "%.2f", sum/n/1000}' "$f")
    printf "%-25s %10s %10s\n" "$name" "${pkg_avg}W" "${core_avg}W"
done

# Generate graphs
echo ""
echo "=== Generating Graphs ==="
if [ -d "$BASE_DIR/.venv" ]; then
    source "$BASE_DIR/.venv/bin/activate"
    python3 "$BASE_DIR/scripts/generate_graphs.py" "$RUN_DIR"
else
    echo "Python venv not found. Run manually:"
    echo "  cd $BASE_DIR && source .venv/bin/activate && python3 scripts/generate_graphs.py $RUN_DIR"
fi

echo ""
echo "=== Complete ==="
echo "Results: $RUN_DIR"
