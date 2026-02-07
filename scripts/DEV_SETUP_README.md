# Dev Mode Auto-Setup for Local Testing

This directory contains scripts that automate the worker setup process for local development, mimicking Alice's privileges.

## What It Does

When you create a new identity in the desktop app and want to test it locally, this script automatically:

1. ✅ **Funds your account** - Transfers 1,000,000 tokens from Alice
2. ✅ **Waits for DID creation** - Monitors the chain for your worker's DID
3. ✅ **Approves credential** - Uses Alice's sudo to approve your worker

## Safety

⚠️ **LOCAL ONLY**: These scripts will ONLY work with local chains (127.0.0.1/localhost). They refuse to run against mainnet or testnet for safety.

## Prerequisites

```bash
cd F:\Work\QX\qxchain\qxchain
npm install --save-dev @polkadot/api
```

## Usage

### Quick Start (Recommended)

1. **Create an identity** in your desktop app
2. **Run the setup script** with your worker address:

**PowerShell:**
```powershell
.\scripts\dev-setup-worker.ps1 5Dy4mGk6qigs7t2ec4Ej64tzngZHBCQvTqf3jLzkEx2aKzGw
```

**Bash/Mac/Linux:**
```bash
node ./scripts/dev-setup-worker.js 5Dy4mGk6qigs7t2ec4Ej64tzngZHBCQvTqf3jLzkEx2aKzGw
```

3. **Start your worker** in the desktop app
4. The script will automatically detect the DID and approve it!

### Manual Steps (If Needed)

If you already have a DID, you can provide it:

```powershell
.\scripts\dev-setup-worker.ps1 5Dy4m... 0x1234...
```

## Output Example

```
🔗 Dev Worker Setup Script
============================================================

⚠️  DEV MODE ONLY - This script is for local testing

📝 Configuration:
   Endpoint: ws://127.0.0.1:9944
   Worker Address: 5Dy4mGk6qigs7t2ec4Ej64tzngZHBCQvTqf3jLzkEx2aKzGw
   Worker DID: (will wait for creation)
   Fund Amount: 1,000,000 tokens

🔗 Connecting to chain: ws://127.0.0.1:9944
✅ Connected to chain
   Chain: Local Testnet
   Block: #37542

👤 Using Alice: 5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY

💰 Step 1: Funding worker account...
✅ Transfer included in block: 0xabcd...
✅ Funded 5Dy4mGk6qigs7t2ec4Ej64tzngZHBCQvTqf3jLzkEx2aKzGw
   Amount: 1,000,000 tokens

🔍 Step 2: Waiting for worker DID to be created...
💡 Start your worker in the desktop app now!

✅ Worker DID detected: 0x94772f97f5f6b539aac74e798bc395119f39603402d0c85bc9eda5dfc5ae2160

🔑 Step 3: Approving worker credential...
✅ Credential issued in block: 0xdef1...
🎉 Worker credential successfully issued!
   Worker DID: 0x9477...
   Sudo execution successful

✨ Worker setup complete!

📋 Summary:
   ✅ Account funded: 5Dy4m...
   ✅ Worker DID: 0x9477...
   ✅ Credential approved for model 0

🚀 Your worker is ready to process tasks!
```

## Frontend Integration (Future)

The Tauri backend has dev helper commands that can trigger this automatically:

```typescript
// In your React component (dev mode only)
import { invoke } from '@tauri-apps/api/core';

async function autoSetupWorker() {
  const result = await invoke('dev_auto_setup_worker', {
    endpoint: 'ws://127.0.0.1:9944'
  });
  console.log(result.message);
}
```

## Troubleshooting

### "Cannot find module '@polkadot/api'"
```bash
cd F:\Work\QX\qxchain\qxchain
npm install --save-dev @polkadot/api
```

### "Credential not found in keychain"
Your seed phrase wasn't stored during identity creation. Try:
1. Sign out in the app
2. Import your recovery phrase again
3. This will re-store it in the keychain

### "Timeout waiting for DID"
The worker didn't create a DID within 5 minutes. Make sure:
1. The account has funds (run step 1 separately if needed)
2. You actually started the worker in the app
3. The chain is running and producing blocks

### Script won't run on mainnet
✅ **This is intentional!** The script only works on local chains for safety.

## Architecture

- **dev-setup-worker.js**: Node.js script using @polkadot/api
- **dev-setup-worker.ps1**: PowerShell wrapper for Windows
- **dev_helpers.rs**: Tauri commands (debug builds only)

## For Production

These scripts and commands are **NOT included** in release builds. They're compile-time gated with `#[cfg(debug_assertions)]`.
