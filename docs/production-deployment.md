# Production Deployment

This guide walks through deploying QXChain validators in production.

## Prerequisites

- Linux server (AMD64 architecture)
- Docker installed
- Azure account (if using Azure Container Apps)
- Basic understanding of blockchain validators

## Step 1: Generate Validator Keys

Each validator needs cryptographic keys for consensus participation.

```bash
./scripts/generate_keys.sh
```

This interactive script will:
1. Install `subkey` (Substrate key generation tool)
2. Generate three types of keys:
   - **Aura key** (SR25519) - for block production
   - **Grandpa key** (Ed25519) - for finality
   - **Node key** (Ed25519) - for P2P networking
3. Save keys to `scripts/node_keys/{validator-name}_{timestamp}.txt`

**IMPORTANT**:
- Keep generated key files secure
- Never commit them to version control
- Back them up in a secure location

### Understanding the Keys

**Aura & Grandpa Keys**:
- Private keys (seed phrases) must be inserted into the validator node via RPC
- Public keys (SS58 addresses) go into the chain specification

**Node Key**:
- Passed as a command-line argument (`--node-key`)
- Determines the node's Peer ID on the P2P network

## Step 2: Update Chain Specification

Edit `node/src/chain_spec/mainnet.rs` and add your validator's public keys:

```rust
authority_keys_from_ss58(
    "5YourAuraPublicKey...",     // Aura (SR25519) - from key file
    "5YourGrandpaPublicKey...",  // Grandpa (Ed25519) - from key file
),
```

Also update the sudo account if needed (typically set to validator-01's Aura key).

## Step 3: Rebuild Chain Specifications

After modifying `mainnet.rs`, regenerate the chain spec files:

```bash
# Rebuild all chain specs (automatically removes existing ones)
./scripts/build_all_chainspecs.sh
```

This script will:
- Remove any existing chainspec files
- Build fresh chainspecs from the current code
- Create both raw and plain versions for each network

Generated files:
- `raw_spec_mainnet.json` - Use this for production validators
- `plain_spec_mainnet.json` - Human-readable version for inspection

## Step 4: Build Production Docker Image

Build the Docker image for AMD64 architecture (required for cloud deployment):

```bash
docker build --platform linux/amd64 --target qxchain-production -t qxchain:production .
```

This takes ~15 minutes and produces an optimized production binary.

> **Note for macOS users**: If testing multi-node setups locally on macOS with linux/amd64 images, be aware that node connectivity may not work properly due to architecture emulation. For local testing, build with your native architecture or test on actual Linux AMD64 machines.

## Step 5: Push to Container Registry

### Azure Container Registry (ACR)

```bash
# Tag for ACR
docker tag qxchain:production qxchain.azurecr.io/qxchain:production

# Login to ACR
az acr login --name qxchain

# Push image
docker push qxchain.azurecr.io/qxchain:production
```

## Step 6: Deploy Validator Node

### Docker (Self-Hosted)

```bash
# Create persistent volume
docker volume create qxchain-validator-01-data

# Run validator
docker run -d \
  --name qxchain-validator-01 \
  -p 30333:30333 \
  -p 9933:9933 \
  -p 9944:9944 \
  -v qxchain-validator-01-data:/data \
  qxchain:production \
  --base-path /data \
  --chain /home/qxchain/chainspecs/raw_spec_mainnet.json \
  --validator \
  --name "qxchain-validator-01" \
  --node-key <YOUR_NODE_KEY_HEX>
```

## Step 7: Insert Validator Keys

Insert keys manually via RPC after the validator is running:

### Azure Container Apps

```bash
# Connect to container
az containerapp exec \
  --name qxchain-validator-01 \
  --resource-group <your-resource-group> \
  --command /bin/bash

# Insert Aura key (inside container)
curl -H "Content-Type: application/json" -d '{"id":1,"jsonrpc":"2.0","method":"author_insertKey","params":["aura","<YOUR_AURA_PHRASE>","<YOUR_AURA_PUBLIC>"]}' http://127.0.0.1:9944

# Insert Grandpa key (inside container)
curl -H "Content-Type: application/json" -d '{"id":1,"jsonrpc":"2.0","method":"author_insertKey","params":["gran","<YOUR_GRANDPA_PHRASE>","<YOUR_GRANDPA_PUBLIC>"]}' http://127.0.0.1:9944

# Exit container
exit
```

### Docker (Self-Hosted)

```bash
# Insert Aura key
docker exec qxchain-validator-01 curl -H "Content-Type: application/json" \
  -d '{"id":1,"jsonrpc":"2.0","method":"author_insertKey","params":["aura","<YOUR_AURA_PHRASE>","<YOUR_AURA_PUBLIC>"]}' \
  http://127.0.0.1:9944

# Insert Grandpa key
docker exec qxchain-validator-01 curl -H "Content-Type: application/json" \
  -d '{"id":1,"jsonrpc":"2.0","method":"author_insertKey","params":["gran","<YOUR_GRANDPA_PHRASE>","<YOUR_GRANDPA_PUBLIC>"]}' \
  http://127.0.0.1:9944
```

Both commands should return: `{"jsonrpc":"2.0","id":1,"result":null}`

## Step 8: Verify Keys Are Loaded

```bash
# Check Aura key
curl -H "Content-Type: application/json" -d '{"id":1,"jsonrpc":"2.0","method":"author_hasKey","params":["<YOUR_AURA_PUBLIC>","aura"]}' http://127.0.0.1:9944

# Check Grandpa key
curl -H "Content-Type: application/json" -d '{"id":1,"jsonrpc":"2.0","method":"author_hasKey","params":["<YOUR_GRANDPA_PUBLIC>","gran"]}' http://127.0.0.1:9944
```

Both should return: `{"jsonrpc":"2.0","result":true,"id":1}`

## Step 9: Lock Down Security

After confirming the validator is working:

1. **Change RPC methods to Safe**:
   - Update `--rpc-methods` from `Unsafe` to `Safe`
   - Redeploy container

2. **Verify key persistence**:
   - Keys are now persisted in `/data/chains/.../keystore/`
   - Will be automatically loaded on restart

3. **Restrict network access**:
   - Only expose P2P port (30333) publicly
   - RPC ports (9933, 9944) should be internal only

## Monitoring & Maintenance

- **Storage**: Monitor `/data` volume usage
- **Logs**: Check for errors or warnings regularly
- **Updates**: Follow runtime upgrade process for chain updates
- **Backups**: Backup `/data` directory regularly (contains keystore)

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for common issues and solutions.