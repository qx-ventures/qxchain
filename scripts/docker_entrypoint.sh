#!/bin/sh
set -e

# Store original arguments to pass to the final exec call
original_args="$@"

# Set default values
base_path='/data'
chain_spec=''

# Parse arguments to find the real --base-path and --chain, handles both
# --key value and --key=value formats.
while [ $# -gt 0 ]; do
  case "$1" in
    --base-path)
      # Check if the next argument exists and is not another option
      if [ -n "$2" ] && ! expr "$2" : '--' > /dev/null; then
        base_path="$2"
        shift
      fi
      ;;
    --base-path=*)
      base_path="${1#*=}"
      ;;
    --chain)
      # Check if the next argument exists and is not another option
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

echo "entrypoint: ensuring permissions for base path: ${base_path}"
mkdir -p "$base_path"
chown -R qxchain:qxchain "$base_path"

# Check if a chain spec was provided and if it's an existing file
if [ -n "$chain_spec" ] && [ -f "$chain_spec" ]; then
    echo "entrypoint: ensuring permissions for chain spec: ${chain_spec}"
    chown qxchain:qxchain "$chain_spec"
fi

# Also check for the hardcoded /tmp/blockchain directory
if [ -d "/tmp/blockchain" ]; then
    chown -R qxchain:qxchain /tmp/blockchain
fi

# Execute qxchain with the original, unmodified arguments
echo "executing: qxchain $original_args"
exec qxchain $original_args
