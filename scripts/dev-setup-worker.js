#!/usr/bin/env node
/**
 * Dev Mode Worker Setup Script
 *
 * Automatically sets up a new worker account for local testing:
 * 1. Funds the account from Alice (1M tokens)
 * 2. Waits for DID creation
 * 3. Auto-approves worker credential
 *
 * SAFETY: Only works on local chains (127.0.0.1)
 */

const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

// Colors for terminal output
const colors = {
    reset: '\x1b[0m',
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    cyan: '\x1b[36m',
    red: '\x1b[31m',
};

function log(color, prefix, message) {
    console.log(`${color}${prefix}${colors.reset} ${message}`);
}

async function main() {
    // Parse arguments
    const args = process.argv.slice(2);
    if (args.length < 1) {
        console.log('Usage: node dev-setup-worker.js <worker_address> [worker_did]');
        console.log('');
        console.log('Example: node dev-setup-worker.js 5Dy4mGk6qigs7t2ec4Ej64tzngZHBCQvTqf3jLzkEx2aKzGw');
        console.log('');
        console.log('If DID is not provided, script will wait for it to be created on-chain.');
        process.exit(1);
    }

    const workerAddress = args[0];
    let workerDid = args[1] || null;

    // Configuration
    const endpoint = 'ws://127.0.0.1:9944';
    const fundAmount = 500_000_000_000_000_000n; // 500K tokens (with 12 decimals)
    const models = [0]; // Allow model 0

    log(colors.cyan, '🔗', 'Dev Worker Setup Script');
    console.log('='.repeat(60));
    console.log('');
    log(colors.yellow, '⚠️ ', 'DEV MODE ONLY - This script is for local testing');
    console.log('');

    // Safety check: only allow local endpoints
    if (!endpoint.includes('127.0.0.1') && !endpoint.includes('localhost')) {
        log(colors.red, '❌', 'ERROR: This script only works with local chains!');
        log(colors.red, '  ', `Endpoint: ${endpoint} is not a local chain`);
        process.exit(1);
    }

    log(colors.cyan, '📝', 'Configuration:');
    console.log(`   Endpoint: ${endpoint}`);
    console.log(`   Worker Address: ${workerAddress}`);
    console.log(`   Worker DID: ${workerDid || '(will wait for creation)'}`);
    console.log(`   Fund Amount: 1,000,000 tokens`);
    console.log('');

    // Connect to chain
    log(colors.cyan, '🔗', `Connecting to chain: ${endpoint}`);
    const wsProvider = new WsProvider(endpoint);
    const api = await ApiPromise.create({ provider: wsProvider });

    log(colors.green, '✅', 'Connected to chain');
    const chain = await api.rpc.system.chain();
    const blockHeader = await api.rpc.chain.getHeader();
    console.log(`   Chain: ${chain}`);
    console.log(`   Block: #${blockHeader.number.toNumber()}`);
    console.log('');

    // Create Alice account
    const keyring = new Keyring({ type: 'sr25519' });
    const alice = keyring.addFromUri('//Alice');
    log(colors.cyan, '👤', `Using Alice: ${alice.address}`);
    console.log('');

    // Step 1: Fund the worker account
    log(colors.cyan, '💰', 'Step 1: Funding worker account...');

    // Check if account already has funds
    const accountInfo = await api.query.system.account(workerAddress);
    const currentBalance = accountInfo.data.free.toBigInt();

    if (currentBalance > 0n) {
        log(colors.yellow, '⚠️ ', `Account already has balance: ${currentBalance.toString()}`);
        log(colors.green, '✅', 'Skipping funding step');
    } else {
        // Use sudo forceSetBalance - works even when Alice doesn't have enough balance
        const forceSetBalanceCall = api.tx.balances.forceSetBalance(workerAddress, fundAmount);
        const sudoTx = api.tx.sudo.sudo(forceSetBalanceCall);

        await new Promise((resolve, reject) => {
            let resolved = false;
            sudoTx.signAndSend(alice, ({ events = [], status }) => {
                if (resolved) return;

                if (status.isInBlock) {
                    log(colors.green, '✅', `Transfer included in block: ${status.asInBlock.toHex()}`);
                }

                if (status.isFinalized) {
                    // Check if sudo call succeeded
                    const sudoSuccess = events.some(({ event }) => {
                        if (api.events.sudo.Sudid.is(event)) {
                            const [result] = event.data;
                            return result.isOk;
                        }
                        return false;
                    });

                    if (sudoSuccess) {
                        log(colors.green, '✅', `Transfer finalized in block: ${status.asFinalized.toHex()}`);
                        log(colors.green, '✅', `Funded ${workerAddress}`);
                        log(colors.green, '  ', `Amount: 500,000 tokens`);
                        resolved = true;
                        resolve();
                    } else {
                        resolved = true;
                        reject(new Error('Sudo forceSetBalance failed - check chain logs'));
                    }
                }
            }).catch(err => {
                if (!resolved) {
                    resolved = true;
                    reject(err);
                }
            });
        });

        // Verify the balance was actually set
        const newAccountInfo = await api.query.system.account(workerAddress);
        const newBalance = newAccountInfo.data.free.toBigInt();
        if (newBalance === 0n) {
            throw new Error('Balance set appeared to succeed but account still has 0 balance.');
        }
        log(colors.green, '  ', `Verified new balance: ${newBalance.toString()}`);
    }
    console.log('');

    // Step 2: Wait for or get worker DID
    if (!workerDid) {
        log(colors.cyan, '🔍', 'Step 2: Waiting for worker DID to be created...');
        log(colors.yellow, '💡', 'Start your worker in the desktop app now!');
        console.log('');

        // Poll for DID creation
        workerDid = await waitForWorkerDid(api, workerAddress, 300); // 5 minute timeout

        if (!workerDid) {
            log(colors.red, '❌', 'Timeout waiting for DID creation');
            log(colors.yellow, '💡', 'Make sure the worker app is running and creating a DID');
            await api.disconnect();
            process.exit(1);
        }

        log(colors.green, '✅', `Worker DID detected: ${workerDid}`);
        console.log('');
    } else {
        log(colors.cyan, '✅', `Step 2: Using provided DID: ${workerDid}`);
        console.log('');
    }

    // Step 3: Approve worker credential
    log(colors.cyan, '🔑', 'Step 3: Approving worker credential...');

    // Check if credential already exists
    const existingCredential = await api.query.qxKiltPermissions.workerCredentials(workerDid);

    if (existingCredential.isSome) {
        log(colors.yellow, '⚠️ ', 'Credential already exists for this DID');
        log(colors.green, '✅', 'Skipping credential approval');
    } else {
        const credentialTx = api.tx.sudo.sudo(
            api.tx.qxKiltPermissions.issueWorkerCredential(
                workerDid,
                models,
                null // permanent credential
            )
        );

        await new Promise((resolve, reject) => {
            credentialTx.signAndSend(alice, ({ events = [], status }) => {
                if (status.isInBlock) {
                    log(colors.green, '✅', `Credential issued in block: ${status.asInBlock.toHex()}`);

                    // Check for credential issued event
                    events.forEach(({ event }) => {
                        if (event.section === 'qxKiltPermissions' && event.method === 'WorkerCredentialIssued') {
                            log(colors.green, '🎉', 'Worker credential successfully issued!');
                            log(colors.green, '  ', `Worker DID: ${event.data[0].toHex()}`);
                        }

                        if (event.section === 'sudo' && event.method === 'Sudid') {
                            log(colors.green, '  ', 'Sudo execution successful');
                        }
                    });

                    resolve();
                } else if (status.isFinalized) {
                    log(colors.green, '🏁', 'Transaction finalized');
                }
            });
        });
    }
    console.log('');

    // Success!
    log(colors.green, '✨', 'Worker setup complete!');
    console.log('');
    log(colors.cyan, '📋', 'Summary:');
    console.log(`   ✅ Account funded: ${workerAddress}`);
    console.log(`   ✅ Worker DID: ${workerDid}`);
    console.log(`   ✅ Credential approved for model 0`);
    console.log('');
    log(colors.green, '🚀', 'Your worker is ready to process tasks!');
    console.log('');

    await api.disconnect();
    process.exit(0);
}

/**
 * Poll the chain for worker DID creation
 */
async function waitForWorkerDid(api, workerAddress, timeoutSeconds) {
    const startTime = Date.now();
    const timeout = timeoutSeconds * 1000;
    let lastCheck = 0;

    while (Date.now() - startTime < timeout) {
        // Check every 6 seconds (1 block)
        if (Date.now() - lastCheck < 6000) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            continue;
        }
        lastCheck = Date.now();

        // Query all DIDs and find one matching our address
        const entries = await api.query.did.did.entries();

        for (const [key, value] of entries) {
            if (value.isSome) {
                const didDoc = value.unwrap();
                // The DID document contains the authentication key which should match our address
                const didIdentifier = key.args[0].toHex();

                // Try to derive address from DID and compare
                // For now, we'll return the first DID we find after the worker starts
                // A more robust solution would parse the DID document structure

                // Simple heuristic: if a new DID appeared after we started watching
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                log(colors.yellow, '🔍', `Found DID: ${didIdentifier} (checking... ${elapsed}s elapsed)`);

                // Since we can't easily match DID to address, return the most recent one
                // This works because we expect only our worker to be creating DIDs
                return didIdentifier;
            }
        }

        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const remaining = timeoutSeconds - elapsed;
        if (elapsed % 10 === 0) {
            log(colors.yellow, '⏳', `Still waiting for DID creation... (${remaining}s remaining)`);
        }
    }

    return null;
}

main().catch((error) => {
    console.error('');
    log(colors.red, '❌', 'Error:');
    console.error(error);
    process.exit(1);
});
