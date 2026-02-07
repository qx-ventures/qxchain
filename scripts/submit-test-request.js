#!/usr/bin/env node
/**
 * Submit Test Inference Request
 *
 * Creates a test inference request to your worker for testing queue functionality
 */

const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

async function main() {
    const endpoint = 'ws://127.0.0.1:9944';
    const workerAddress = '5HKj2mpyyiWR9VTu88Ube6px8eKgvXiWQ2GHJ4UqC9FJDWhj'; // Your worker
    const prompt = 'Explain what a blockchain is in simple terms';
    const maxTokens = 100;

    console.log('🔗 Connecting to chain:', endpoint);
    const wsProvider = new WsProvider(endpoint);
    const api = await ApiPromise.create({ provider: wsProvider });

    console.log('✅ Connected to chain');
    console.log('📦 Chain:', await api.rpc.system.chain());

    // Use Alice as customer (has tokens)
    const keyring = new Keyring({ type: 'sr25519' });
    const alice = keyring.addFromUri('//Alice');

    console.log('\n👤 Customer (Alice):', alice.address);
    console.log('🤖 Target Worker:', workerAddress);
    console.log('💬 Prompt:', prompt);
    console.log('🎯 Max Tokens:', maxTokens);

    // Submit inference request
    console.log('\n📝 Submitting inference request...');
    const tx = api.tx.qxAi.submitRequest(
        workerAddress,
        prompt,
        maxTokens
    );

    await tx.signAndSend(alice, ({ events = [], status }) => {
        console.log('📊 Status:', status.type);

        if (status.isInBlock) {
            console.log('✅ Included in block:', status.asInBlock.toHex());

            let requestId = null;
            events.forEach(({ event: { data, method, section } }) => {
                console.log(`   📢 ${section}.${method}`);

                if (section === 'qxAi' && method === 'RequestSubmitted') {
                    requestId = data[0].toString();
                    console.log('\n🎉 SUCCESS! Request submitted!');
                    console.log('   Request ID:', requestId);
                    console.log('   Customer:', data[1].toString());
                    console.log('   Worker:', data[2].toString());
                }

                if (section === 'qxAi' && method === 'RequestAssigned') {
                    console.log('\n✅ Request assigned to worker queue!');
                    console.log('   Worker should pick it up shortly...');
                }

                if (method === 'ExtrinsicFailed') {
                    console.error('\n❌ Request submission failed!');
                    const [dispatchError] = data;
                    if (dispatchError.isModule) {
                        const decoded = api.registry.findMetaError(dispatchError.asModule);
                        console.error(`   Error: ${decoded.section}.${decoded.name}: ${decoded.docs}`);
                    }
                }
            });

            if (requestId) {
                console.log('\n📱 Check your desktop worker app - request should appear in queue!');
                console.log('🔄 Worker will automatically process it and submit results.');
            }
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
