# QX Chain Scripts

Simple scripts for setting up and running the QX Chain opML environment.

## Quick Start

```bash
./setup_qx_chain.sh  # Complete setup
```

## Setup Scripts

- **`setup_qx_chain.sh`** - Complete setup (dependencies, Ollama, build)
- **`check_dependencies.sh`** - Install Rust, Python, Ollama
- **`setup_ollama.sh`** - Setup Ollama service and models
- **`build_chain.sh`** - Build the QX Chain node
- **`test_setup.sh`** - Test all components

## Service Scripts (Run in Separate Terminals)

- **`start_chain.sh`** - Start QX Chain (shows logs)
- **`start_worker.sh`** - Start worker (shows logs)
- **`start_validator.sh`** - Start validator (shows logs)

## Usage

### 1. Setup (one time)
```bash
./setup_qx_chain.sh
```

### 2. Run Services (separate terminals)
```bash
# Terminal 1
./start_chain.sh

# Terminal 2  
./start_worker.sh

# Terminal 3
./start_validator.sh
```

### 3. Stop Services
Press `Ctrl+C` in each terminal

## Service Information

- **QX Chain**: `ws://localhost:9944`
- **Ollama API**: `http://localhost:11434`  
- **Worker API**: `http://localhost:8000` (dynamic port)

## Testing

```bash
# Test inference
./test_inference.py

# Or manually
curl -X POST http://localhost:8000/inference \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello", "model_id": 0}'
```

## Python Scripts

- **`ollama_worker.py`** - Worker that handles inference
- **`validator.py`** - Validator for transactions  
- **`test_inference.py`** - Test inference functionality

## Logs

Logs show in terminal and save to `logs/` directory.

## Troubleshooting

1. **Build issues**: Run `./check_dependencies.sh`
2. **Ollama issues**: Re-run `./setup_ollama.sh`  
3. **Port conflicts**: Stop with `Ctrl+C` and restart
