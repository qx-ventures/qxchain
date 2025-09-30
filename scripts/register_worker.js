#!/usr/bin/env node
/**
 * Register Bob as a worker using polkadot.js
 * This bypasses the Python codec issues by using the proper JS library
 */

const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

async function main() {
  console.log('='.repeat(60));
  console.log('Register Worker on QxChain');
  console.log('='.repeat(60));
  console.log();

  // Connect to local node
  const provider = new WsProvider('ws://localhost:9944');
  const api = await ApiPromise.create({ provider });

  console.log('✅ Connected to chain:', (await api.rpc.system.chain()).toString());
  console.log('📦 Current block:', (await api.rpc.chain.getHeader()).number.toNumber());
  console.log();

  // Create keyring
  const keyring = new Keyring({ type: 'sr25519' });

  // Bob will be the worker
  const bob = keyring.addFromUri('//Bob');
  console.log('Worker (Bob):', bob.address);
  console.log();

  // Register worker
  console.log('📝 Submitting register_worker transaction...');

  try {
    const unsub = await api.tx.mlInference
      .registerWorker()
      .signAndSend(bob, ({ status, events }) => {
        if (status.isInBlock) {
          console.log('✅ Transaction included in block:', status.asInBlock.toHex());

          // Check events
          events.forEach(({ event }) => {
            const { section, method, data } = event;
            console.log(`   Event: ${section}.${method}`, data.toString());

            if (section === 'mlInference' && method === 'WorkerRegistered') {
              console.log('🎉 WORKER REGISTERED SUCCESSFULLY!');
            }
          });
        } else if (status.isFinalized) {
          console.log('✅ Transaction finalized:', status.asFinalized.toHex());
          unsub();

          // Query to verify
          checkWorkerRegistration(api, bob.address).then(() => {
            process.exit(0);
          });
        } else if (status.isDropped || status.isInvalid || status.isUsurped) {
          console.log('❌ Transaction failed:', status.type);
          unsub();
          process.exit(1);
        } else {
          console.log('⏳ Transaction status:', status.type);
        }
      });
  } catch (error) {
    console.error('❌ Error submitting transaction:', error.message);
    process.exit(1);
  }
}

async function checkWorkerRegistration(api, address) {
  console.log();
  console.log('🔍 Verifying registration...');

  try {
    // Query Workers storage
    const result = await api.query.mlInference.workers(address);
    console.log('Workers storage for', address, ':', result.toString());

    if (result.toJSON()) {
      console.log('✅ WORKER IS REGISTERED ON CHAIN!');
    } else {
      console.log('❌ Worker not found in storage');
    }
  } catch (error) {
    console.error('Error querying storage:', error.message);
  }
}

main().catch(console.error);