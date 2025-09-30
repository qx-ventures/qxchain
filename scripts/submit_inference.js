#!/usr/bin/env node
/**
 * Submit an inference request to the worker
 */

const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

async function main() {
  console.log('='.repeat(60));
  console.log('Submit Inference Request to QxChain');
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

  // Alice is the customer
  const alice = keyring.addFromUri('//Alice');
  // Worker node is running with Bob's keypair
  const bob = keyring.addFromUri('//Bob');

  console.log('Customer (Alice):', alice.address);
  console.log('Worker (Bob):', bob.address);
  console.log('💡 Note: Workers use signature-based identity');
  console.log();

  // Prepare inference request - target Bob since that's the worker
  const prompt = "Explain quantum computing in one sentence";
  const modelId = 1;

  console.log('📝 Submitting inference request...');
  console.log('   Prompt:', prompt);
  console.log('   Model ID:', modelId);
  console.log('   Target Worker:', bob.address);
  console.log();

  try {
    const unsub = await api.tx.mlInference
      .submitRequest(bob.address, prompt, modelId)
      .signAndSend(alice, ({ status, events }) => {
        if (status.isInBlock) {
          console.log('✅ Transaction included in block:', status.asInBlock.toHex());

          // Check events
          events.forEach(({ event }) => {
            const { section, method, data } = event;
            console.log(`   Event: ${section}.${method}`, data.toString());

            if (section === 'mlInference' && method === 'RequestSubmitted') {
              console.log('🎉 INFERENCE REQUEST SUBMITTED!');
              const [requestId] = data;
              console.log('   Request ID:', requestId.toString());
            }

            if (section === 'mlInference' && method === 'RequestAssigned') {
              console.log('✅ Request assigned to worker');
            }
          });
        } else if (status.isFinalized) {
          console.log('✅ Transaction finalized:', status.asFinalized.toHex());
          unsub();

          // Wait a bit for worker to process
          console.log();
          console.log('⏳ Waiting 10 seconds for worker to process the request...');
          setTimeout(() => {
            checkInferenceResults(api).then(() => {
              process.exit(0);
            });
          }, 10000);
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

async function checkInferenceResults(api) {
  console.log();
  console.log('🔍 Checking for inference results...');
  console.log('='.repeat(60));

  try {
    // Query NextRequestId to see how many requests were submitted
    const nextRequestId = await api.query.mlInference.nextRequestId();
    console.log('Total requests submitted:', nextRequestId.toString());

    // Query NextInferenceId to see how many inferences completed
    const nextInferenceId = await api.query.mlInference.nextInferenceId();
    console.log('Total inferences completed:', nextInferenceId.toString());
    console.log();

    // Check inference results
    if (nextInferenceId.toNumber() > 0) {
      console.log('✅ Inference results found!');

      for (let i = 0; i < nextInferenceId.toNumber(); i++) {
        const result = await api.query.mlInference.inferenceResults(i);
        if (result.isSome) {
          const data = result.unwrap();
          console.log();
          console.log(`Inference #${i}:`);
          console.log('  Request ID:', data.requestId.toString());
          console.log('  Worker:', data.worker.toString());
          console.log('  Status:', data.status.toString());
          console.log('  Output:', Buffer.from(data.output).toString('utf8'));
          console.log('  Submitted at block:', data.submittedAt.toString());
        }
      }
    } else {
      console.log('⚠️  No inference results yet. Worker may still be processing.');
      console.log('   Check worker logs for processing status.');
    }

    // Check worker queue
    const bob = new Keyring({ type: 'sr25519' }).addFromUri('//Bob');
    const queue = await api.query.mlInference.workerQueues(bob.address);
    console.log();
    console.log('Worker queue size:', queue.length);
    if (queue.length > 0) {
      console.log('Pending requests in queue:', queue.toJSON());
    }

  } catch (error) {
    console.error('Error querying results:', error.message);
  }
}

main().catch(console.error);