#!/usr/bin/env node
/**
 * Quick Approve Worker Credential
 *
 * Approves the worker DID: 0x9efe98486e7af357e7d3739766003c0125c7f358ec4620258dafe51a6c674556
 */

const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

async function main() {
    const endpoint = 'ws://127.0.0.1:9944';
    const workerDid = '0x9efe98486e7af357e7d3739766003c0125c7f358ec4620258dafe51a6c674556';
    const models = [0]; // Allow model 0
    const validityPeriod = null; // Permanent

    console.log('🔗 Connecting to chain:', endpoint);
    const wsProvider = new WsProvider(endpoint);
    const api = await ApiPromise.create({ provider: wsProvider });

    console.log('✅ Connected to chain');
    console.log('📦 Chain:', await api.rpc.system.chain());

    // Create Alice account (has sudo access)
    const keyring = new Keyring({ type: 'sr25519' });
    const alice = keyring.addFromUri('//Alice');

    console.log('\n👤 Using Alice (sudo) account:', alice.address);
    console.log('🆔 Approving Worker DID:', workerDid);

    // Issue credential via sudo
    const tx = api.tx.sudo.sudo(
        api.tx.qxKiltPermissions.issueWorkerCredential(
            workerDid,
            models,
            validityPeriod
        )
    );

    console.log('\n🚀 Submitting credential approval...');

    await tx.signAndSend(alice, ({ events = [], status }) => {
        console.log('📊 Status:', status.type);

        if (status.isInBlock) {
            console.log('✅ Included in block:', status.asInBlock.toHex());

            events.forEach(({ event: { data, method, section } }) => {
                console.log(`   📢 ${section}.${method}`);

                if (section === 'qxKiltPermissions' && method === 'WorkerCredentialIssued') {
                    console.log('\n🎉 SUCCESS! Worker credential approved!');
                    console.log('   DID:', data[0].toHex());
                    console.log('\n✅ Go back to the desktop app - it should detect the credential now!');
                }

                if (method === 'ExtrinsicFailed') {
                    console.error('   ❌ Approval failed!');
                    const [dispatchError] = data;
                    if (dispatchError.isModule) {
                        const decoded = api.registry.findMetaError(dispatchError.asModule);
                        console.error(`   Error: ${decoded.section}.${decoded.name}: ${decoded.docs}`);
                    }
                }
            });
        } else if (status.isFinalized) {
            console.log('🏁 Finalized in block:', status.asFinalized.toHex());
            process.exit(0);
        }
    });
}

main().catch((error) => {
    console.error('❌ Error:', error);
    process.exit(1);
});
