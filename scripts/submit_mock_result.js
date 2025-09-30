#!/usr/bin/env node
/**
 * Submit a mock inference result for testing validator
 */

const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

async function main() {
  console.log('='.repeat(60));
  console.log('Submit Mock Inference Result (for Validator Testing)');
  console.log('='.repeat(60));
  console.log();

  // Connect to local node
  const endpoint = process.env.CHAIN_ENDPOINT || 'ws://localhost:9944';
  const provider = new WsProvider(endpoint);
  const api = await ApiPromise.create({ provider });

  console.log('✅ Connected to chain:', (await api.rpc.system.chain()).toString());
  console.log('📦 Current block:', (await api.rpc.chain.getHeader()).number.toNumber());
  console.log();

  const keyring = new Keyring({ type: 'sr25519' });

  // Alice submits request
  const alice = keyring.addFromUri('//Alice');
  // Bob acts as worker
  const bob = keyring.addFromUri('//Bob');

  console.log('Customer (Alice):', alice.address);
  console.log('Worker (Bob):', bob.address);
  console.log();

  // First submit an inference request
  console.log('📝 Step 1: Submitting inference request...');
  const prompt = "Explain quantum computing in one sentence";
  const modelId = 1;

  await new Promise((resolve, reject) => {
    api.tx.mlInference
      .submitRequest(bob.address, prompt, modelId)
      .signAndSend(alice, ({ status, events }) => {
        if (status.isFinalized) {
          console.log('✅ Request finalized');
          resolve();
        }
      });
  });

  // Wait a moment
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Now submit the inference result as Bob (the worker)
  console.log();
  console.log('📝 Step 2: Submitting inference result as worker...');
  const requestId = 0; // First request
  const output = "Quantum computing uses quantum mechanics principles like superposition and entanglement to process information.";

  await new Promise((resolve, reject) => {
    api.tx.mlInference
      .submitInference(requestId, output)
      .signAndSend(bob, ({ status, events, dispatchError }) => {
        if (dispatchError) {
          if (dispatchError.isModule) {
            const decoded = api.registry.findMetaError(dispatchError.asModule);
            console.log(`❌ Error: ${decoded.section}.${decoded.name}`);
          } else {
            console.log('❌ Error:', dispatchError.toString());
          }
          reject(dispatchError);
          return;
        }

        if (status.isInBlock) {
          console.log('✅ Result included in block');
        }

        if (status.isFinalized) {
          console.log('✅ Result finalized');

          events.forEach(({ event }) => {
            const { section, method } = event;
            if (section === 'mlInference' && method === 'InferenceSubmitted') {
              console.log();
              console.log('🎉 SUCCESS!');
              console.log('   Inference result submitted to chain');
              console.log('   Ready for validator to challenge!');
              console.log();
            }
          });

          resolve();
        }
      });
  });

  // Check the result
  await new Promise(resolve => setTimeout(resolve, 2000));

  const nextInferenceId = await api.query.mlInference.nextInferenceId();
  console.log('📊 Total inferences in system:', nextInferenceId.toString());

  if (nextInferenceId.toNumber() > 0) {
    const inferenceId = nextInferenceId.toNumber() - 1;
    const inference = await api.query.mlInference.inferenceResults(inferenceId);

    if (inference.isSome) {
      const inferenceData = inference.unwrap();
      console.log('✅ Inference result stored:');
      console.log('   ID:', inferenceId);
      console.log('   Worker:', inferenceData.worker.toString());
      console.log('   Output:', Buffer.from(inferenceData.output).toString('utf8').substring(0, 80) + '...');
      console.log('   Status:', inferenceData.status.toString());
      console.log();
      console.log('👉 Now you can test validator challenge with:');
      console.log('   node scripts/test_validator_simple.js');
    }
  }

  process.exit(0);
}

main().catch(error => {
  console.error('❌ Error:', error.message);
  process.exit(1);
});
