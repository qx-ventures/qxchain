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
Chain Spec Usage (chain_spec/mainnet.rs)
================================================================================
authority_keys_from_ss58(
    "${AURA_SS58}",  // Aura
    "${GRANDPA_SS58}"   // Grandpa
),

================================================================================
Insert Keys Commands (for running node)
================================================================================
# Insert Aura key
curl -H "Content-Type: application/json" \\
  --data '{"jsonrpc":"2.0","method":"author_insertKey","params":["aura","${AURA_PHRASE}","${AURA_PUBLIC}"],"id":1}' \\
  http://localhost:9944

# Insert Grandpa key
curl -H "Content-Type: application/json" \\
  --data '{"jsonrpc":"2.0","method":"author_insertKey","params":["gran","${GRANDPA_PHRASE}","${GRANDPA_PUBLIC}"],"id":1}' \\
  http://localhost:9944

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
    echo -e "${BLUE}Chain spec code snippet:${NC}"
    echo ""
    echo "authority_keys_from_ss58("
    echo "    \"${AURA_SS58}\",  // Aura"
    echo "    \"${GRANDPA_SS58}\"   // Grandpa"
    echo "),"
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

# Show main menu
main_menu
