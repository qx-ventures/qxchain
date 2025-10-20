#!/bin/bash

# QXChain Key Generation Script
# This script helps generate Aura (SR25519) and Grandpa (Ed25519) keys for validators

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYS_DIR="$SCRIPT_DIR/node_keys"

# Create keys directory if it doesn't exist
mkdir -p "$KEYS_DIR"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  QXChain Validator Key Generation Tool${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check if subkey is installed
check_subkey() {
    if command -v subkey &> /dev/null; then
        echo -e "${GREEN}✓ subkey is already installed${NC}"
        subkey --version
        return 0
    else
        echo -e "${YELLOW}✗ subkey is not installed${NC}"
        return 1
    fi
}

# Check if jq is installed (needed for JSON parsing)
check_jq() {
    if command -v jq &> /dev/null; then
        echo -e "${GREEN}✓ jq is already installed${NC}"
        return 0
    else
        echo -e "${YELLOW}✗ jq is not installed (needed for node key generation)${NC}"
        echo ""
        echo "Install jq with:"
        echo "  macOS:   brew install jq"
        echo "  Ubuntu:  sudo apt-get install jq"
        echo "  Other:   https://jqlang.github.io/jq/download/"
        return 1
    fi
}

# Install subkey
install_subkey() {
    echo ""
    echo -e "${BLUE}Installing subkey...${NC}"
    echo ""
    echo "Choose installation method:"
    echo "1) Cargo install (builds from source, takes 5-10 minutes)"
    echo "2) Use Docker (faster, but requires Docker)"
    read -p "Choice [1-2]: " install_method

    case $install_method in
        1)
            echo ""
            echo "This may take several minutes as it compiles from source."
            echo ""

            # Try stable versions in order of recency
            TAGS=("polkadot-stable2506" "polkadot-stable2503" "polkadot-stable2412")

            for TAG in "${TAGS[@]}"; do
                echo -e "${YELLOW}Trying to install with $TAG...${NC}"
                if cargo install --force subkey --git https://github.com/paritytech/polkadot-sdk --tag "$TAG" --locked; then
                    echo ""
                    echo -e "${GREEN}✓ subkey installed successfully with $TAG!${NC}"
                    subkey --version
                    return 0
                else
                    echo -e "${YELLOW}Failed with $TAG, trying next version...${NC}"
                fi
            done

            echo -e "${RED}✗ Failed to install subkey with all stable versions${NC}"
            echo -e "${YELLOW}You can try Docker method instead or install manually${NC}"
            exit 1
            ;;
        2)
            if ! command -v docker &> /dev/null; then
                echo -e "${RED}✗ Docker is not installed${NC}"
                echo "Install Docker from: https://docs.docker.com/get-docker/"
                exit 1
            fi

            echo -e "${GREEN}✓ Using Docker for subkey${NC}"
            echo ""
            echo "Creating subkey wrapper script..."

            # Create ~/.local/bin if it doesn't exist
            mkdir -p "$HOME/.local/bin"

            # Create wrapper script
            cat > "$HOME/.local/bin/subkey" << 'WRAPPER_EOF'
#!/bin/bash
docker run --rm -i docker.io/parity/subkey:latest "$@"
WRAPPER_EOF

            chmod +x "$HOME/.local/bin/subkey"

            echo -e "${GREEN}✓ Docker subkey wrapper installed to ~/.local/bin/subkey${NC}"
            echo -e "${YELLOW}Make sure ~/.local/bin is in your PATH${NC}"

            # Test it
            if "$HOME/.local/bin/subkey" --version &>/dev/null; then
                echo -e "${GREEN}✓ subkey is working!${NC}"
            fi
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
}

# Generate Aura key (SR25519)
generate_aura_key() {
    echo ""
    echo -e "${BLUE}Generating Aura Key (SR25519 - Block Production)...${NC}"
    echo ""
    subkey generate --scheme sr25519 --output-type json
    echo ""
}

# Generate Grandpa key (Ed25519)
generate_grandpa_key() {
    echo ""
    echo -e "${BLUE}Generating Grandpa Key (Ed25519 - Finality)...${NC}"
    echo ""
    subkey generate --scheme ed25519 --output-type json
    echo ""
}

# Generate complete validator set
generate_validator_set() {
    echo ""
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  Generating Complete Validator Key Set${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""

    read -p "Enter validator/node name (e.g., validator-01, alice, etc.): " NODE_NAME

    if [ -z "$NODE_NAME" ]; then
        echo -e "${RED}Node name cannot be empty${NC}"
        return
    fi

    # Generate timestamp
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    FILENAME="${KEYS_DIR}/${NODE_NAME}_${TIMESTAMP}.txt"

    echo ""
    echo -e "${YELLOW}1. AURA KEY (SR25519 - Block Production)${NC}"
    echo ""
    AURA_OUTPUT=$(subkey generate --scheme sr25519)
    echo "$AURA_OUTPUT"
    AURA_SS58=$(echo "$AURA_OUTPUT" | grep "SS58 Address" | awk '{print $3}')
    AURA_PUBLIC=$(echo "$AURA_OUTPUT" | grep "Public key (hex)" | awk '{print $4}')
    AURA_ACCOUNT=$(echo "$AURA_OUTPUT" | grep "Account ID" | awk '{print $3}')
    AURA_SEED=$(echo "$AURA_OUTPUT" | grep "Secret seed" | awk '{print $3}')
    AURA_PHRASE=$(echo "$AURA_OUTPUT" | grep "Secret phrase" | cut -d'`' -f2)

    echo ""
    echo -e "${YELLOW}2. GRANDPA KEY (Ed25519 - Finality)${NC}"
    echo ""
    GRANDPA_OUTPUT=$(subkey generate --scheme ed25519)
    echo "$GRANDPA_OUTPUT"
    GRANDPA_SS58=$(echo "$GRANDPA_OUTPUT" | grep "SS58 Address" | awk '{print $3}')
    GRANDPA_PUBLIC=$(echo "$GRANDPA_OUTPUT" | grep "Public key (hex)" | awk '{print $4}')
    GRANDPA_ACCOUNT=$(echo "$GRANDPA_OUTPUT" | grep "Account ID" | awk '{print $3}')
    GRANDPA_SEED=$(echo "$GRANDPA_OUTPUT" | grep "Secret seed" | awk '{print $3}')
    GRANDPA_PHRASE=$(echo "$GRANDPA_OUTPUT" | grep "Secret phrase" | cut -d'`' -f2)

    echo ""
    echo -e "${YELLOW}3. NODE KEY (Ed25519 - P2P Networking)${NC}"
    echo ""

    # Check if jq is available for JSON parsing
    if command -v jq &> /dev/null; then
        NODE_OUTPUT=$(subkey generate --scheme ed25519 --output-type json)
        echo "$NODE_OUTPUT" | jq '.'
        NODE_SECRET=$(echo "$NODE_OUTPUT" | jq -r '.secretSeed' | sed 's/0x//')
        NODE_PUBLIC=$(echo "$NODE_OUTPUT" | jq -r '.publicKey')
        NODE_SS58=$(echo "$NODE_OUTPUT" | jq -r '.ss58Address')

        echo ""
        echo -e "${BLUE}Node key generated. Peer ID will be computed when node starts.${NC}"
        echo -e "${YELLOW}To get Peer ID: Start the node and check logs for 'Local node identity'${NC}"
        PEER_ID="<WILL_BE_COMPUTED_ON_STARTUP>"
    else
        echo -e "${YELLOW}⚠ jq not found - generating node key without JSON parsing${NC}"
        NODE_OUTPUT=$(subkey generate --scheme ed25519)
        echo "$NODE_OUTPUT"
        NODE_SECRET=$(echo "$NODE_OUTPUT" | grep "Secret seed" | awk '{print $3}' | sed 's/0x//')
        NODE_PUBLIC=$(echo "$NODE_OUTPUT" | grep "Public key" | grep -v "SS58" | awk '{print $4}')
        NODE_SS58=$(echo "$NODE_OUTPUT" | grep "SS58 Address" | awk '{print $3}')
        PEER_ID="<START_NODE_TO_GET_PEER_ID>"
    fi

    # Save to file
    cat > "$FILENAME" << EOF
================================================================================
QXChain Validator Keys - ${NODE_NAME}
Generated: $(date)
================================================================================

WARNING: Keep this file secure! Never commit to version control!

================================================================================
AURA KEY (SR25519 - Block Production)
================================================================================
Secret Phrase: ${AURA_PHRASE}
Secret Seed:   ${AURA_SEED}
Public Key:    ${AURA_PUBLIC}
Account ID:    ${AURA_ACCOUNT}
SS58 Address:  ${AURA_SS58}

================================================================================
GRANDPA KEY (Ed25519 - Finality)
================================================================================
Secret Phrase: ${GRANDPA_PHRASE}
Secret Seed:   ${GRANDPA_SEED}
Public Key:    ${GRANDPA_PUBLIC}
Account ID:    ${GRANDPA_ACCOUNT}
SS58 Address:  ${GRANDPA_SS58}

================================================================================
NODE KEY (Ed25519 - P2P Networking)
================================================================================
Node Key (hex): ${NODE_SECRET}
Public Key:     ${NODE_PUBLIC}
Peer ID:        ${PEER_ID} (get from logs after first start)

================================================================================
Chain Spec Usage (chain_spec/mainnet.rs)
================================================================================
authority_keys_from_ss58(
    "${AURA_SS58}",  // Aura
    "${GRANDPA_SS58}"   // Grandpa
),

================================================================================
Bootnode (get Peer ID from logs after first start)
================================================================================
"/dns/your-domain.com/tcp/30333/p2p/<PEER_ID>"

================================================================================
Docker Command
================================================================================
--node-key ${NODE_SECRET}

================================================================================
Insert Keys (via docker exec ... curl)
================================================================================
["aura","${AURA_PHRASE}","${AURA_PUBLIC}"]
["gran","${GRANDPA_PHRASE}","${GRANDPA_PUBLIC}"]

================================================================================
EOF

    echo ""
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}  Validator Keys Generated Successfully!${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo ""
    echo -e "${GREEN}✓ Keys saved to: ${FILENAME}${NC}"
    echo ""
    echo -e "${YELLOW}IMPORTANT: Keep this file secure!${NC}"
    echo ""
    echo -e "${BLUE}Chain Spec:${NC}"
    echo "authority_keys_from_ss58(\"${AURA_SS58}\", \"${GRANDPA_SS58}\"),"
    echo ""
    echo -e "${BLUE}Node Key:${NC} --node-key ${NODE_SECRET}"
    echo ""
}

# Inspect a key
inspect_key() {
    echo ""
    read -p "Enter the key to inspect (secret phrase, seed, or public key): " KEY_INPUT
    echo ""

    echo "Select key scheme:"
    echo "1) SR25519 (Aura)"
    echo "2) Ed25519 (Grandpa)"
    read -p "Choice [1-2]: " SCHEME_CHOICE

    case $SCHEME_CHOICE in
        1)
            SCHEME="sr25519"
            ;;
        2)
            SCHEME="ed25519"
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            return
            ;;
    esac

    echo ""
    echo -e "${BLUE}Inspecting key with scheme: $SCHEME${NC}"
    echo ""
    subkey inspect --scheme "$SCHEME" "$KEY_INPUT"
    echo ""
}

# Main menu
main_menu() {
    while true; do
        echo ""
        echo -e "${BLUE}What would you like to do?${NC}"
        echo ""
        echo "1) Generate Aura key (SR25519) for block production"
        echo "2) Generate Grandpa key (Ed25519) for finality"
        echo "3) Generate complete validator key set (Aura + Grandpa)"
        echo "4) Inspect an existing key"
        echo "5) Check/Install subkey"
        echo "6) Exit"
        echo ""
        read -p "Enter your choice [1-6]: " choice

        case $choice in
            1)
                generate_aura_key
                ;;
            2)
                generate_grandpa_key
                ;;
            3)
                generate_validator_set
                ;;
            4)
                inspect_key
                ;;
            5)
                check_subkey || install_subkey
                ;;
            6)
                echo ""
                echo -e "${GREEN}Goodbye!${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid choice. Please try again.${NC}"
                ;;
        esac
    done
}

# Run the script
echo ""
if ! check_subkey; then
    echo ""
    read -p "Would you like to install subkey now? [y/N]: " install_choice
    if [[ $install_choice =~ ^[Yy]$ ]]; then
        install_subkey
    else
        echo ""
        echo -e "${YELLOW}You can install subkey later with either:${NC}"
        echo "1) Cargo: cargo install --force subkey --git https://github.com/paritytech/polkadot-sdk --tag polkadot-stable2506 --locked"
        echo "2) Docker: docker run --rm -i docker.io/parity/subkey:latest --version"
        echo ""
        exit 1
    fi
fi

echo ""
if ! check_jq; then
    echo ""
    echo -e "${YELLOW}jq is required for node key generation${NC}"
    echo -e "${YELLOW}Please install it before generating validator keys${NC}"
    echo ""
    read -p "Continue anyway? (node key generation will be skipped) [y/N]: " continue_choice
    if [[ ! $continue_choice =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Show main menu
main_menu
