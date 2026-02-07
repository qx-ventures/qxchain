#!/usr/bin/env node
/**
 * Check available extrinsics
 */

const { ApiPromise, WsProvider } = require('@polkadot/api');

async function main() {
    console.log('🔗 Connecting...');
    const provider = new WsProvider('ws://127.0.0.1:9944');
    const api = await ApiPromise.create({ provider });

    console.log(`✅ Connected to: ${await api.rpc.system.chain()}`);
    console.log('\n📝 Available balances extrinsics:');

    const balancesTx = api.tx.balances;
    for (const method in balancesTx) {
        if (typeof balancesTx[method] === 'function') {
            console.log(`   - balances.${method}`);
        }
    }

    console.log('\n📝 Checking sudo:');
    if (api.tx.sudo) {
        console.log('   ✅ Sudo pallet available');
        for (const method in api.tx.sudo) {
            if (typeof api.tx.sudo[method] === 'function') {
                console.log(`   - sudo.${method}`);
            }
        }
    } else {
        console.log('   ❌ Sudo pallet NOT available');
    }

    await api.disconnect();
}

main().catch(console.error);
