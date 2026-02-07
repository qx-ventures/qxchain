#!/usr/bin/env node
/**
 * Issue Worker Credential Script
 *
 * This script uses polkadot.js API to issue a worker credential
 * for the worker DID waiting for approval.
 */

const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

async function main() {
    // Configuration
    const endpoint = 'ws://127.0.0.1:9944';
    const workerDid = '0x2e3fb4c297a84c5cebc0e78257d213d0927ccc7596044c6ba013dd05522aacba'; // Alice-seeded DID
    const models = [0]; // Allow model 0
    const validityPeriod = null; // null = permanent, or use number of blocks

    console.log('🔗 Connecting to chain:', endpoint);
    const wsProvider = new WsProvider(endpoint);
    const api = await ApiPromise.create({ provider: wsProvider });

    console.log('✅ Connected to chain');
    console.log('📦 Chain:', await api.rpc.system.chain());
    console.log('🔢 Block:', (await api.rpc.chain.getHeader()).number.toNumber());

    // Create Alice account (has sudo access on localnet)
    const keyring = new Keyring({ type: 'sr25519' });
    const alice = keyring.addFromUri('//Alice');

    console.log('\n👤 Using Alice account:', alice.address);
    console.log('🔑 Alice has sudo access on localnet');

    // Create the extrinsic
    console.log('\n📝 Creating issue_worker_credential extrinsic...');
    console.log('   Worker DID:', workerDid);
    console.log('   Models:', models);
    console.log('   Validity:', validityPeriod || 'Permanent');

    // Issue credential via sudo
    const tx = api.tx.sudo.sudo(
        api.tx.qxKiltPermissions.issueWorkerCredential(
            workerDid,
            models,
            validityPeriod
        )
    );

    console.log('\n🚀 Submitting transaction...');

    // Sign and send
    const unsub = await tx.signAndSend(alice, ({ events = [], status }) => {
        console.log('📊 Transaction status:', status.type);

        if (status.isInBlock) {
            console.log('✅ Transaction included in block:', status.asInBlock.toHex());

            // Check events
            events.forEach(({ event: { data, method, section } }) => {
                console.log(`   📢 ${section}.${method}:`, data.toString());

                if (section === 'qxKiltPermissions' && method === 'WorkerCredentialIssued') {
                    console.log('\n🎉 SUCCESS! Worker credential issued!');
                    console.log('   Worker DID:', data[0].toHex());
                }

                if (section === 'sudo' && method === 'Sudid') {
                    console.log('   ✅ Sudo execution successful');
                }

                if (method === 'ExtrinsicFailed') {
                    console.error('   ❌ Transaction failed!');
                }
            });
        } else if (status.isFinalized) {
            console.log('🏁 Transaction finalized in block:', status.asFinalized.toHex());
            console.log('\n✅ DONE! The worker can now start processing tasks.');
            console.log('   Go back to the desktop UI and it should proceed automatically.');
            unsub();
            process.exit(0);
        }
    });
}

main().catch((error) => {
    console.error('❌ Error:', error);
    process.exit(1);
});
