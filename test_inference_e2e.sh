#!/bin/bash

echo "🚀 Starting ML Inference End-to-End Test"
echo "========================================="

# Kill any existing processes
pkill -f qxchain || true
sleep 2

# Step 1: Start the main chain
echo "📦 Step 1: Starting main chain on port 9933..."
./target/release/qxchain --dev > main_chain.log 2>&1 &
MAIN_PID=$!
echo "Main chain PID: $MAIN_PID"
sleep 5

# Step 2: Register Bob as a worker
echo "👷 Step 2: Registering Bob as worker..."
cd scripts
node register_worker.js
cd ..
sleep 3

# Step 3: Submit inference request to Bob
echo "📝 Step 3: Submitting inference request to Bob's queue..."
cd customer
python3 substrate_client.py
cd ..
sleep 3

# Step 4: Start worker with Bob's keypair
echo "🤖 Step 4: Starting worker with Bob's keypair..."
./target/release/qxchain --dev --node-role worker --ai-endpoint http://host.docker.internal:11434 --ai-model llama3.2:3b --rpc-port 9945 > worker.log 2>&1 &
WORKER_PID=$!
echo "Worker PID: $WORKER_PID"

# Step 5: Monitor for processing
echo "🔍 Step 5: Monitoring worker activity..."
sleep 5

# Check worker logs for activity
echo "📊 Worker logs:"
tail -50 worker.log | grep -E "queue|request|Processing|llama|inference|Found" || tail -20 worker.log

# Check if request is still in queue
echo "📋 Checking request status..."
cd customer
python3 check_requests.py 2>/dev/null || echo "Need to install substrate-interface"
cd ..

echo "========================================="
echo "✅ Test complete!"
echo "Main chain PID: $MAIN_PID"
echo "Worker PID: $WORKER_PID"
echo "Check worker.log and main_chain.log for details"