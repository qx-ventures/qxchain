#!/usr/bin/env node
/**
 * Check account balance on local chain
 */

const { ApiPromise, WsProvider } = require('@polkadot/api');

async function main() {
    const address = process.argv[2] || '5Dy4mGk6qigs7t2ec4Ej64tzngZHBCQvTqf3jLzkEx2aKzGw';

    console.log('🔗 Connecting to ws://127.0.0.1:9944...');
    const provider = new WsProvider('ws://127.0.0.1:9944');
    const api = await ApiPromise.create({ provider });

    console.log(`✅ Connected to: ${await api.rpc.system.chain()}`);
    console.log(`📊 Block: #${await api.rpc.chain.getHeader().then(h => h.number.toNumber())}`);
    console.log('');

    // Check Alice balance
    const aliceAddr = '5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY';
    const aliceAccount = await api.query.system.account(aliceAddr);
    const aliceBalance = aliceAccount.data.free.toBigInt();
    console.log(`👑 Alice (${aliceAddr}):`);
    console.log(`   Balance: ${formatBalance(aliceBalance)} tokens`);
    console.log('');

    // Check worker account balance
    const account = await api.query.system.account(address);
    const balance = account.data.free.toBigInt();
    const reserved = account.data.reserved.toBigInt();
    const frozen = account.data.frozen.toBigInt();

    console.log(`🤖 Worker (${address}):`);
    console.log(`   Free Balance: ${formatBalance(balance)} tokens`);
    console.log(`   Reserved: ${formatBalance(reserved)} tokens`);
    console.log(`   Frozen: ${formatBalance(frozen)} tokens`);
    console.log(`   Total: ${formatBalance(balance + reserved)} tokens`);
    console.log('');

    // Check if worker has DID (if pallet exists)
    try {
        if (api.query.did && api.query.did.did) {
            const did = await api.query.did.did(address);
            if (did.isSome) {
                const didData = did.unwrap();
                console.log('✅ Worker DID exists!');
                console.log(`   DID: 0x${Buffer.from(didData.identifier).toString('hex')}`);
                console.log('');
            } else {
                console.log('⚠️  Worker DID not created yet');
                console.log('');
            }
        } else {
            console.log('⚠️  DID pallet not available on this chain');
            console.log('');
        }
    } catch (e) {
        console.log(`⚠️  Could not query DID: ${e.message}`);
        console.log('');
    }

    // Check transaction history
    console.log('📜 Recent transfers to this account:');
    const transfers = await api.query.system.events();
    let found = false;
    transfers.forEach(({ event }) => {
        if (api.events.balances.Transfer.is(event)) {
            const [from, to, amount] = event.data;
            if (to.toString() === address) {
                console.log(`   ✅ Received ${formatBalance(amount.toBigInt())} from ${from.toString().substring(0, 10)}...`);
                found = true;
            }
        }
    });
    if (!found) {
        console.log('   No recent transfers found in current block events');
    }

    await api.disconnect();
}

function formatBalance(balance) {
    const decimals = 12;
    const divisor = 10n ** BigInt(decimals);
    const whole = balance / divisor;
    const fractional = balance % divisor;
    const fracStr = fractional.toString().padStart(decimals, '0').substring(0, 4);
    return `${whole}.${fracStr}`;
}

main().catch(console.error);
