#!/usr/bin/env node
/**
 * Simple transfer test - try different methods
 */

const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

async function main() {
    const address = process.argv[2] || '5Dy4mGk6qigs7t2ec4Ej64tzngZHBCQvTqf3jLzkEx2aKzGw';

    console.log('🔗 Connecting...');
    const provider = new WsProvider('ws://127.0.0.1:9944');
    const api = await ApiPromise.create({ provider });

    console.log(`✅ Connected to: ${await api.rpc.system.chain()}`);

    // Setup Alice
    const keyring = new Keyring({ type: 'sr25519' });
    const alice = keyring.addFromUri('//Alice');
    console.log(`👑 Alice: ${alice.address}`);

    // Amount: 500K tokens
    const amount = 500_000_000_000_000_000n;

    console.log('\n📊 Before transfer:');
    let accountInfo = await api.query.system.account(address);
    console.log(`   Worker balance: ${accountInfo.data.free.toString()}`);
    let aliceInfo = await api.query.system.account(alice.address);
    console.log(`   Alice balance: ${aliceInfo.data.free.toString()}`);

    // Try sudo forceSetBalance - this just sets the balance directly
    console.log('\n💰 Attempting sudo forceSetBalance...');
    const forceSetBalanceCall = api.tx.balances.forceSetBalance(address, amount);
    const sudoTx = api.tx.sudo.sudo(forceSetBalanceCall);

    const result = await new Promise((resolve, reject) => {
        let resolved = false;
        sudoTx.signAndSend(alice, ({ events = [], status }) => {
            if (resolved) return;

            console.log(`   Status: ${status.type}`);

            if (status.isInBlock) {
                console.log(`   ✅ In block: ${status.asInBlock.toHex()}`);

                // Log all events
                events.forEach(({ event }) => {
                    const { section, method, data } = event;
                    console.log(`   Event: ${section}.${method}`, data.toString());

                    if (api.events.system.ExtrinsicFailed.is(event)) {
                        const [dispatchError] = data;
                        let errorInfo = dispatchError.toString();

                        if (dispatchError.isModule) {
                            try {
                                const decoded = api.registry.findMetaError(dispatchError.asModule);
                                errorInfo = `${decoded.section}.${decoded.name}: ${decoded.docs}`;
                            } catch (e) {
                                // ignore
                            }
                        }
                        console.log(`   ❌ ExtrinsicFailed: ${errorInfo}`);
                    }
                });
            }

            if (status.isFinalized) {
                const failed = events.some(({ event }) =>
                    api.events.system.ExtrinsicFailed.is(event)
                );

                resolved = true;
                if (failed) {
                    reject(new Error('Transfer failed'));
                } else {
                    console.log(`   ✅ Finalized: ${status.asFinalized.toHex()}`);
                    resolve();
                }
            }
        }).catch(err => {
            if (!resolved) {
                resolved = true;
                reject(err);
            }
        });
    });

    console.log('\n📊 After transfer:');
    accountInfo = await api.query.system.account(address);
    console.log(`   Worker balance: ${accountInfo.data.free.toString()}`);
    aliceInfo = await api.query.system.account(alice.address);
    console.log(`   Alice balance: ${aliceInfo.data.free.toString()}`);

    await api.disconnect();
    console.log('\n✅ Done!');
}

main().catch(e => {
    console.error('\n❌ Error:', e.message);
    process.exit(1);
});
