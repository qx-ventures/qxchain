const { ApiPromise, WsProvider } = require('@polkadot/api');

async function main() {
    const provider = new WsProvider('ws://localhost:9944');
    const api = await ApiPromise.create({ provider });

    console.log("============================================================");
    console.log("Checking Bob's Queue on Main Chain");
    console.log("============================================================\n");

    const bob = '5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty';

    // Check if Bob is registered
    const isRegistered = await api.query.mlInference.workers(bob);
    console.log(`Bob registration status: ${isRegistered.toString()}`);

    // Check Bob's queue
    const queue = await api.query.mlInference.workerQueues(bob);
    console.log(`\nBob's queue: ${JSON.stringify(queue.toJSON())}`);

    // Check NextRequestId
    const nextId = await api.query.mlInference.nextRequestId();
    console.log(`\nNext Request ID: ${nextId.toString()}`);

    // If there are requests, fetch details
    if (queue && queue.length > 0) {
        for (const reqId of queue.toJSON()) {
            const request = await api.query.mlInference.inferenceRequests(reqId);
            if (request.isSome) {
                console.log(`\nRequest #${reqId} details:`);
                console.log(JSON.stringify(request.unwrap().toJSON(), null, 2));
            }
        }
    }

    await api.disconnect();
}

main().catch(console.error);