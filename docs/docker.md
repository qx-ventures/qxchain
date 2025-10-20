# Docker Deployment

QXChain provides production-ready Docker images for easy deployment.

## Docker Targets

The Dockerfile has two build targets:

### `qxchain-production` (Production)
- Optimized binary built with `--profile production`
- Thin LTO enabled for smaller binary size
- Non-root user (qxchain:qxchain, UID/GID 10001)
- Includes only production chainspecs

### `qxchain-local` (Development)
- Full workspace build with `--profile release`
- Includes all testing tools
- Pre-built localnet chainspec for quick testing

## Building Images

### Production Image

```bash
# For cloud deployment (AMD64)
docker build --platform linux/amd64 --target qxchain-production -t qxchain:production .

# For local testing (matches your architecture)
docker build --target qxchain-production -t qxchain:production .
```

> **⚠️ macOS Compatibility Warning**: When running linux/amd64 Docker containers on macOS (both Apple Silicon and Intel), peer-to-peer connectivity between validator nodes may fail. This is due to architecture emulation and network translation layers. For proper multi-node testing on macOS, use native architecture builds or deploy all nodes to the same platform.

### Local Development Image

```bash
docker build --target qxchain-local -t qxchain:local .
```

## Running Containers

### Single Validator (Production)

```bash
docker run -d \
  --name qxchain-validator \
  -p 30333:30333 \
  -p 9933:9933 \
  -p 9944:9944 \
  -v qxchain-data:/data \
  qxchain:production \
  --base-path /data \
  --chain /home/qxchain/chainspecs/raw_spec_mainnet.json \
  --validator \
  --name "My Validator" \
  --node-key <YOUR_NODE_KEY>
```

### Single Validator (Local Development)

```bash
docker run -d \
  --name qxchain-dev \
  -p 30333:30333 \
  -p 9933:9933 \
  -p 9944:9944 \
  -v qxchain-dev-data:/data \
  qxchain:local \
  --base-path /data \
  --chain /localnet.json \
  --alice \
  --unsafe-force-node-key-generation
```

## Docker Compose

For multi-node local testing, use Docker Compose:

```bash
# Start 4-node network
docker-compose up -d

# View logs
docker-compose logs -f

# Stop network
docker-compose down

# Clean up (removes volumes)
docker-compose down -v
```

## Port Mapping

- **30333**: P2P networking (libp2p)
- **9933**: HTTP RPC endpoint
- **9944**: WebSocket RPC endpoint
- **9615**: Prometheus metrics (optional)

## Volume Management

### Persistent Storage

Always use volumes for production to persist blockchain data and keystores:

```bash
# Create named volume
docker volume create qxchain-validator-01-data

# Use in container
-v qxchain-validator-01-data:/data
```

### Inspecting Volumes

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect qxchain-validator-01-data

# Backup volume
docker run --rm -v qxchain-validator-01-data:/data -v $(pwd):/backup alpine tar czf /backup/qxchain-backup.tar.gz /data
```

## Key Management

For production deployments, keys should be inserted via RPC after the node is running:

```bash
# Insert Aura key
docker exec <container-name> curl -H "Content-Type: application/json" \
  -d '{"id":1,"jsonrpc":"2.0","method":"author_insertKey","params":["aura","<AURA_PHRASE>","<AURA_PUBLIC>"]}' \
  http://127.0.0.1:9944

# Insert Grandpa key
docker exec <container-name> curl -H "Content-Type: application/json" \
  -d '{"id":1,"jsonrpc":"2.0","method":"author_insertKey","params":["gran","<GRANDPA_PHRASE>","<GRANDPA_PUBLIC>"]}' \
  http://127.0.0.1:9944
```

Keys are then persisted in the `/data` volume and will be automatically loaded on container restart.

## Networking

### Known Issues

- **macOS with linux/amd64 containers**: Node discovery and P2P connectivity may not work reliably when running linux/amd64 containers on macOS due to architecture emulation. Nodes may connect initially but fail to maintain stable peer connections.
- **Solution**: For local development on macOS, build containers matching your native architecture (arm64 for Apple Silicon, amd64 for Intel).

### Custom Networks

For multi-node deployments, create a custom Docker network:

```bash
# Create network
docker network create qxchain-net

# Run validators on custom network
docker run -d \
  --name validator-01 \
  --network qxchain-net \
  -p 30333:30333 \
  qxchain:production \
  --base-path /data \
  --validator

docker run -d \
  --name validator-02 \
  --network qxchain-net \
  -p 30334:30333 \
  qxchain:production \
  --base-path /data \
  --validator \
  --bootnodes /dns/validator-01/tcp/30333/p2p/<PEER_ID>
```


## Best Practices

1. **Always use named volumes** for production
2. **Never expose RPC ports** publicly (use reverse proxy with auth)
3. **Monitor container logs** regularly
4. **Backup volumes** before updates
5. **Use specific image tags** (not `latest`) for production
6. **Limit container resources** using `--cpus` and `--memory`
7. **Enable automatic restart**: `--restart unless-stopped`