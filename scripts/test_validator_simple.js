#!/usr/bin/env node
/**
 * Simple test: Validator challenges without registration
 * Tests signature-based identity for validators
 */

const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

async function main() {
  console.log('='.repeat(60));
  console.log('Test Validator Challenge (Signature-Based Identity)');
  console.log('='.repeat(60));
  console.log();

  // Connect to worker chain (port 9944)
  const provider = new WsProvider('ws://localhost:9944');
  const api = await ApiPromise.create({ provider });

  console.log('✅ Connected to chain:', (await api.rpc.system.chain()).toString());
  console.log('📦 Current block:', (await api.rpc.chain.getHeader()).number.toNumber());
  console.log();

  const keyring = new Keyring({ type: 'sr25519' });
  const charlie = keyring.addFromUri('//Charlie'); // Validator

  console.log('🛡️  Validator (Charlie):', charlie.address);
  console.log('💡 Validator uses signature-based identity - NO registration needed!');
  console.log();

  // Check if there are any inferences to challenge
  const nextInferenceId = await api.query.mlInference.nextInferenceId();
  console.log('Total inferences in system:', nextInferenceId.toString());

  if (nextInferenceId.toNumber() === 0) {
    console.log('⚠️  No inferences to challenge yet.');
    console.log('   Submit an inference first using: node scripts/submit_inference.js');
    process.exit(0);
  }

  const inferenceId = nextInferenceId.toNumber() - 1; // Challenge the last inference
  const inference = await api.query.mlInference.inferenceResults(inferenceId);

  if (inference.isNone) {
    console.log('❌ Inference not found');
    process.exit(1);
  }

  const inferenceData = inference.unwrap();
  console.log('✅ Found inference to challenge:');
  console.log('   Inference ID:', inferenceId);
  console.log('   Worker:', inferenceData.worker.toString());
  console.log('   Output:', Buffer.from(inferenceData.output).toString('utf8').substring(0, 80) + '...');
  console.log('   Status:', inferenceData.status.toString());
  console.log();

  // Validator challenges WITHOUT pre-registration
  console.log('🛡️  Validator challenging inference (signature-based identity)...');
  const expectedOutput = "A different answer";

  try {
    const unsub = await api.tx.mlInference
      .challengeInference(inferenceId, expectedOutput)
      .signAndSend(charlie, ({ status, events, dispatchError }) => {
        if (dispatchError) {
          if (dispatchError.isModule) {
            const decoded = api.registry.findMetaError(dispatchError.asModule);
            console.log(`❌ Error: ${decoded.section}.${decoded.name}: ${decoded.docs}`);
          } else {
            console.log('❌ Error:', dispatchError.toString());
          }
          unsub();
          process.exit(1);
        }

        if (status.isInBlock) {
          console.log('✅ Challenge transaction included in block');

          events.forEach(({ event }) => {
            const { section, method, data } = event;
            console.log(`   Event: ${section}.${method}`);

            if (section === 'mlInference' && method === 'InferenceChallenged') {
              console.log();
              console.log('🎉🎉🎉 SUCCESS! 🎉🎉🎉');
              console.log('   Validator challenged inference WITHOUT pre-registration!');
              console.log('   Identity was proven by transaction signature alone!');
              console.log();
            }
          });
        } else if (status.isFinalized) {
          console.log('✅ Challenge finalized');
          unsub();

          // Check validator activity tracking
          setTimeout(async () => {
            const validatorActivity = await api.query.mlInference.validatorLastActivity(charlie.address);
            console.log('📊 Validator Activity Tracking:');
            if (validatorActivity.isSome) {
              console.log('   ✅ Activity recorded at block:', validatorActivity.unwrap().toString());
              console.log('   ✅ Signature-based identity system working perfectly!');
              console.log();
              console.log('='.repeat(60));
              console.log('✅ TEST PASSED: Validators work without registration!');
              console.log('='.repeat(60));
            }
            process.exit(0);
          }, 2000);
        }
      });
  } catch (error) {
    console.error('❌ Error submitting challenge:', error.message);
    process.exit(1);
  }
}

main().catch(error => {
  console.error('❌ Error:', error.message);
  process.exit(1);
});
