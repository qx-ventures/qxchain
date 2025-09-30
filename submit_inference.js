const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

async function main() {
    const provider = new WsProvider('ws://localhost:9944');
    const api = await ApiPromise.create({ provider });

    console.log("============================================================");
    console.log("Submit Inference Request to Bob");
    console.log("============================================================\n");

    // Create keypair
    const keyring = new Keyring({ type: 'sr25519' });
    const alice = keyring.addFromUri('//Alice');
    const bob = '5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty';

    // Check if Bob is registered
    const isRegistered = await api.query.mlInference.workers(bob);
    console.log('Bob registration status: ' + isRegistered.toString());

    // Submit inference request
    const prompt = "What is artificial intelligence in one simple sentence?";
    console.log('\\n📝 Submitting inference request: "' + prompt + '"');

    const unsub = await api.tx.mlInference
        .submitRequest(bob, prompt, 0)  // model_id = 0
        .signAndSend(alice, ({ status, events }) => {
            if (status.isInBlock) {
                console.log('⏳ Transaction included at blockHash ' + status.asInBlock);
            } else if (status.isFinalized) {
                console.log('✅ Transaction finalized at blockHash ' + status.asFinalized);

                events.forEach(({ phase, event: { data, method, section } }) => {
                    if (section === 'mlInference' && method === 'InferenceRequestSubmitted') {
                        console.log('\\n🎉 Inference request submitted!');
                        console.log('   Request ID: ' + data[0].toString());
                        console.log('   Customer: ' + data[1].toString());
                        console.log('   Worker: ' + data[2].toString());
                    }
                });

                // Check Bob's queue
                api.query.mlInference.workerQueues(bob).then(queue => {
                    console.log('\\n📋 Bob\'s queue now has ' + queue.length + ' request(s): ' + JSON.stringify(queue.toJSON()));
                    unsub();
                    process.exit(0);
                });
            }
        });
}

main().catch(console.error);