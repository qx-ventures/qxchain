#!/bin/bash

# This script builds all chain specifications from the source code.
# It removes any existing chainspec files and creates fresh ones to ensure
# they reflect the current state of the chain configuration in the code.

set -e

raw_mainnet="chainspecs/raw_spec_mainnet.json"
plain_mainnet="chainspecs/plain_spec_mainnet.json"
raw_localnet="chainspecs/raw_spec_localnet.json"
plain_localnet="chainspecs/plain_spec_localnet.json"
raw_localnet_single="chainspecs/raw_spec_localnet_single.json"
plain_localnet_single="chainspecs/plain_spec_localnet_single.json"

buildspec() {
  local chain="$1"
  shift
  ./target/debug/qxchain build-spec --chain "$chain" --disable-default-bootnode "$@"
}

update_spec() {
  local chain="$1"
  local raw_path="$2"
  local plain_path="$3"

  # Remove existing chainspecs to force fresh generation
  echo "*** Removing existing chainspecs for '$chain'..."
  rm -f "$raw_path" "$plain_path"

  echo "*** Creating new chainspec for '$chain'..."

  # Build new chainspecs
  buildspec "$chain" >"$plain_path"
  buildspec "$chain" --raw >"$raw_path"

  echo "*** New chainspec created for '$chain'"
}

# SCRIPT

echo "*** Building node..."
cargo build -p qxchain

update_spec mainnet "$raw_mainnet" "$plain_mainnet"
update_spec localnet "$raw_localnet" "$plain_localnet"
update_spec localnet_single "$raw_localnet_single" "$plain_localnet_single"

echo "*** Done!"