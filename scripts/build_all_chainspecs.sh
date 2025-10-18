#!/bin/bash

# The genesis is not allowed to change. Since the wasm genesis will change
# depending on the system architecture used, we need to extract the genesis from
# the old chain specs and insert them into the new chain specs to ensure there
# are no genesis mismatch issues.

# This script updates the chain spec files keeping the genesis unchanged.

set -e

raw_mainnet="chainspecs/raw_spec_mainnet.json"
plain_mainnet="chainspecs/plain_spec_mainnet.json"
raw_localnet="chainspecs/raw_spec_localnet.json"
plain_localnet="chainspecs/plain_spec_localnet.json"
raw_localnet_single="chainspecs/raw_spec_localnet_single.json"
plain_localnet_single="chainspecs/plain_spec_localnet_single.json"

save_genesis() {
  jq -r ".genesis" "$1" >"$2"
}

buildspec() {
  local chain="$1"
  shift
  ./target/debug/qxchain build-spec --chain "$chain" --disable-default-bootnode "$@"
}

# Update genesis in new chainspecs using the extracted genesis data from the
# temporary files
update_genesis() {
  jq --slurpfile genesis "$1" '.genesis = $genesis[0]' "$2" >"$3"
}

update_spec() {
  local chain="$1"
  local raw_path="$2"
  local plain_path="$3"

  # Check if the chainspec files exist already
  if [ ! -f "$raw_path" ] || [ ! -f "$plain_path" ]; then
    echo "*** Creating new chainspec for '$chain' (no existing spec to preserve)..."

    # Build new chainspecs
    buildspec "$chain" >"$plain_path"
    buildspec "$chain" --raw >"$raw_path"

    echo "*** New chainspec created for '$chain'"
  else
    raw_genesis_temp=$(mktemp)
    plain_genesis_temp=$(mktemp)
    raw_spec_temp=$(mktemp)
    plain_spec_temp=$(mktemp)

    echo "*** Backing up genesis for '$chain'..."

    save_genesis "$raw_path" "$raw_genesis_temp"
    save_genesis "$plain_path" "$plain_genesis_temp"

    echo "*** Building new chainspec for '$chain'..."

    # Build new chainspecs
    buildspec "$chain" >"$plain_spec_temp"
    buildspec "$chain" --raw >"$raw_spec_temp"

    echo "*** Restoring genesis in '$chain'..."

    update_genesis "$raw_genesis_temp" "$raw_spec_temp" "$raw_path"
    update_genesis "$plain_genesis_temp" "$plain_spec_temp" "$plain_path"

    # cleanup
    rm -f "$raw_genesis_temp" "$plain_genesis_temp" "$raw_spec_temp" \
      "$plain_spec_temp"
  fi
}

# SCRIPT

echo "*** Building node..."
cargo build -p qxchain

update_spec mainnet "$raw_mainnet" "$plain_mainnet"
update_spec localnet "$raw_localnet" "$plain_localnet"
update_spec localnet_single "$raw_localnet_single" "$plain_localnet_single"

echo "*** Done!"