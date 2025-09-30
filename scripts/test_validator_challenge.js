#!/usr/bin/env node
/**
 * Test validator challenge with signature-based identity
 * This script:
 * 1. Submits an inference request from Alice to Bob (worker)
 * 2. Waits for Bob to complete the inference
 * 3. Charlie (validator) challenges the inference with signature-based identity
 */

const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

async function main() {
  console.log('='.repeat(60));
  console.log('Test Validator Challenge (Signature-Based Identity)');
  console.log('='.repeat(60));
  console.log();

  // Connect to worker chain (port 9944)
  const workerProvider = new WsProvider('ws://localhost:9944');
  const workerApi = await ApiPromise.create({ provider: workerProvider });

  // Connect to validator chain (port 9945)
  const validatorProvider = new WsProvider('ws://localhost:9945');
  const validatorApi = await ApiPromise.create({ provider: validatorProvider });

  console.log('✅ Connected to worker chain:', (await workerApi.rpc.system.chain()).toString());
  console.log('✅ Connected to validator chain:', (await validatorApi.rpc.system.chain()).toString());
  console.log();

  // Create keyring
  const keyring = new Keyring({ type: 'sr25519' });
  const alice = keyring.addFromUri('//Alice');
  const bob = keyring.addFromUri('//Bob');
  const charlie = keyring.addFromUri('//Charlie'); // Validator

  console.log('👤 Customer (Alice):', alice.address);
  console.log('🔧 Worker (Bob):', bob.address);
  console.log('🛡️  Validator (Charlie):', charlie.address);
  console.log('💡 Note: No registration needed - identity proven by signature!');
  console.log();

  // Step 1: Submit inference request
  console.log('📝 Step 1: Submitting inference request to worker...');
  const prompt = "What is 2+2?";
  const modelId = 1;

  let requestId;
  const unsub = await workerApi.tx.mlInference
    .submitRequest(bob.address, prompt, modelId)
    .signAndSend(alice, ({ status, events }) => {
      if (status.isInBlock) {
        events.forEach(({ event }) => {
          if (event.section === 'mlInference' && event.method === 'RequestSubmitted') {
            requestId = event.data[0].toString();
            console.log('✅ Request submitted! Request ID:', requestId);
          }
        });
      } else if (status.isFinalized) {
        unsub();
      }
    });

  // Wait for request to be submitted
  await new Promise(resolve => setTimeout(resolve, 3000));

  // Step 2: Wait for worker to process
  console.log();
  console.log('⏳ Step 2: Waiting for worker to process request...');
  await new Promise(resolve => setTimeout(resolve, 10000));

  // Check if inference completed
  const nextInferenceId = await workerApi.query.mlInference.nextInferenceId();
  console.log('Total inferences completed:', nextInferenceId.toString());

  if (nextInferenceId.toNumber() === 0) {
    console.log('⚠️  No inference completed yet. Check worker logs.');
    process.exit(0);
  }

  const inferenceId = 0; // First inference
  const inference = await workerApi.query.mlInference.inferenceResults(inferenceId);

  if (inference.isNone) {
    console.log('❌ Inference not found');
    process.exit(1);
  }

  const inferenceData = inference.unwrap();
  console.log('✅ Inference completed!');
  console.log('   Inference ID:', inferenceId);
  console.log('   Worker:', inferenceData.worker.toString());
  console.log('   Output:', Buffer.from(inferenceData.output).toString('utf8').substring(0, 100) + '...');
  console.log('   Status:', inferenceData.status.toString());

  // Step 3: Validator challenges the inference
  console.log();
  console.log('🛡️  Step 3: Validator challenging inference (no registration needed)...');

  const expectedOutput = "The answer is 4";

  const challengeUnsub = await validatorApi.tx.mlInference
    .challengeInference(inferenceId, expectedOutput)
    .signAndSend(charlie, ({ status, events }) => {
      if (status.isInBlock) {
        console.log('✅ Challenge transaction included in block');

        events.forEach(({ event }) => {
          const { section, method, data } = event;
          console.log(`   Event: ${section}.${method}`);

          if (section === 'mlInference' && method === 'InferenceChallenged') {
            console.log('🎉 VALIDATOR SUCCESSFULLY CHALLENGED INFERENCE!');
            console.log('   Validator identity proven by signature alone - no registration!');
          }
        });
      } else if (status.isFinalized) {
        console.log('✅ Challenge finalized');
        challengeUnsub();

        // Check validator activity tracking
        setTimeout(async () => {
          const validatorActivity = await validatorApi.query.mlInference.validatorLastActivity(charlie.address);
          console.log();
          console.log('📊 Validator Activity Tracking:');
          if (validatorActivity.isSome) {
            console.log('   ✅ Validator activity recorded at block:', validatorActivity.unwrap().toString());
            console.log('   ✅ Signature-based identity system working!');
          }

          process.exit(0);
        }, 2000);
      }
    });
}

main().catch(error => {
  console.error('❌ Error:', error.message);
  process.exit(1);
});
