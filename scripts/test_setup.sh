#!/bin/bash

# QX Chain Test Setup Script
# Tests all components of the QX Chain setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CHAIN_PORT=9944
OLLAMA_PORT=11434
WORKER_API_PORT=8000

echo -e "${BLUE}🧪 Running QX Chain setup tests...${NC}"

# Test Ollama
echo -e "${YELLOW}Testing Ollama...${NC}"
ollama_test=$(curl -s -X POST http://localhost:$OLLAMA_PORT/api/generate \
    -H "Content-Type: application/json" \
    -d '{"model": "gemma3:4b", "prompt": "Hello", "stream": false}' \
    | jq -r '.response' 2>/dev/null || echo "ERROR")

if [ "$ollama_test" != "ERROR" ] && [ ! -z "$ollama_test" ]; then
    echo -e "${GREEN}✅ Ollama test passed${NC}"
else
    echo -e "${RED}❌ Ollama test failed${NC}"
    exit 1
fi

# Test QX Chain RPC
echo -e "${YELLOW}Testing QX Chain RPC...${NC}"
chain_test=$(curl -s -X POST http://localhost:$CHAIN_PORT \
    -H "Content-Type: application/json" \
    -d '{"id":1,"jsonrpc":"2.0","method":"system_health","params":[]}' \
    | jq -r '.result.isSyncing' 2>/dev/null || echo "ERROR")

if [ "$chain_test" = "false" ] || [ "$chain_test" = "true" ]; then
    echo -e "${GREEN}✅ QX Chain RPC test passed${NC}"
else
    echo -e "${RED}❌ QX Chain RPC test failed${NC}"
    exit 1
fi

# Test Worker API
echo -e "${YELLOW}Testing Worker API...${NC}"
worker_status=$(curl -s http://localhost:$WORKER_API_PORT/status | jq -r '.registered' 2>/dev/null || echo "false")

if [ "$worker_status" = "true" ]; then
    echo -e "${GREEN}✅ Worker API test passed${NC}"
else
    echo -e "${RED}❌ Worker API test failed${NC}"
    exit 1
fi

# Test inference
echo -e "${YELLOW}Testing inference...${NC}"
inference_test=$(curl -s -X POST http://localhost:$WORKER_API_PORT/inference \
    -H "Content-Type: application/json" \
    -d '{"prompt": "What are the zoo operating hours?", "model_id": 0}' \
    | jq -r '.response' 2>/dev/null || echo "ERROR")

if [ "$inference_test" != "ERROR" ] && [ ! -z "$inference_test" ]; then
    echo -e "${GREEN}✅ Inference test passed${NC}"
else
    echo -e "${RED}❌ Inference test failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 All tests passed! QX Chain setup is working correctly.${NC}"

echo ""
echo -e "${BLUE}📝 Sample inference command:${NC}"
echo -e "${YELLOW}curl -X POST http://localhost:$WORKER_API_PORT/inference \\${NC}"
echo -e "${YELLOW}  -H \"Content-Type: application/json\" \\${NC}"
echo -e "${YELLOW}  -d '{\"prompt\": \"What are the zoo operating hours?\", \"model_id\": 0}'${NC}"
