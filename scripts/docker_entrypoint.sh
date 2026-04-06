#!/bin/sh

# Store original arguments to pass to the final exec call
original_args="$@"

# Set default values
base_path='/data'
chain_spec=''
chain_id='qxchain_mainnet'

# Parse arguments to find the real --base-path and --chain
while [ $# -gt 0 ]; do
  case "$1" in
    --base-path)
      if [ -n "$2" ] && ! expr "$2" : '--' > /dev/null; then
        base_path="$2"
        shift
      fi
      ;;
    --base-path=*)
      base_path="${1#*=}"
      ;;
    --chain)
      if [ -n "$2" ] && ! expr "$2" : '--' > /dev/null; then
        chain_spec="$2"
        shift
      fi
      ;;
    --chain=*)
      chain_spec="${1#*=}"
      ;;
  esac
  shift
done

# Determine chain_id from chain_spec filename
if echo "$chain_spec" | grep -q "localnet"; then
  chain_id='qxchain_local'
elif echo "$chain_spec" | grep -q "mainnet"; then
  chain_id='qxchain_mainnet'
fi

echo "entrypoint: setting up base path: ${base_path}"
echo "entrypoint: chain_id: ${chain_id}"

# Create base path and all required subdirectories
mkdir -p "$base_path"
mkdir -p "$base_path/chains/$chain_id/keystore"

# Set permissions
chown -R qxchain:qxchain "$base_path" 2>/dev/null || true
chmod -R 777 "$base_path" 2>/dev/null || true

# Insert validator keys from environment variables if provided
# Keys are inserted into the keystore directory before starting the node
# Format: filename = {key_type_hex}{public_key_without_0x}
# Content: JSON string of the seed phrase
keystore_path="$base_path/chains/$chain_id/keystore"

if [ -n "$AURA_PHRASE" ] && [ -n "$AURA_PUBLIC" ]; then
    # aura key type = 61757261 (hex for "aura")
    public_hex=$(echo "$AURA_PUBLIC" | sed 's/^0x//')
    keystore_file="$keystore_path/61757261${public_hex}"
    echo "\"$AURA_PHRASE\"" > "$keystore_file"
    chmod 600 "$keystore_file" 2>/dev/null || true
    echo "entrypoint: inserted AURA key -> $keystore_file"
fi

if [ -n "$GRANDPA_PHRASE" ] && [ -n "$GRANDPA_PUBLIC" ]; then
    # gran key type = 6772616e (hex for "gran")
    public_hex=$(echo "$GRANDPA_PUBLIC" | sed 's/^0x//')
    keystore_file="$keystore_path/6772616e${public_hex}"
    echo "\"$GRANDPA_PHRASE\"" > "$keystore_file"
    chmod 600 "$keystore_file" 2>/dev/null || true
    echo "entrypoint: inserted GRANDPA key -> $keystore_file"
fi

# Handle chain spec permissions
if [ -n "$chain_spec" ] && [ -f "$chain_spec" ]; then
    chown qxchain:qxchain "$chain_spec" 2>/dev/null || true
    chmod 644 "$chain_spec" 2>/dev/null || true
fi

# Execute qxchain
echo "executing: qxchain $original_args"
exec qxchain $original_args
