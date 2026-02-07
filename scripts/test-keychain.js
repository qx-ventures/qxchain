#!/usr/bin/env node
/**
 * Test if we can retrieve the seed from keychain using the Rust function
 */

const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

async function testKeychain(address) {
    console.log(`\n🔑 Testing keychain access for: ${address}`);
    console.log('='.repeat(70));

    // The Rust app stores with this format
    const appId = 'qxchain_desktop_worker';
    const credKey = `seed_phrase_${address}`;
    const targetName = `${appId}:${credKey}`;

    console.log(`\n📝 Looking for Windows credential:`);
    console.log(`   Target: ${targetName}`);
    console.log('');

    // Check with cmdkey
    const { execSync } = require('child_process');
    try {
        const output = execSync('cmdkey /list', { encoding: 'utf8' });

        if (output.includes(targetName)) {
            console.log('✅ Credential FOUND in Windows Credential Manager!');
            console.log('');

            // Show the entry
            const lines = output.split('\n');
            let found = false;
            for (let i = 0; i < lines.length; i++) {
                if (lines[i].includes(targetName)) {
                    console.log('   ' + lines[i].trim());
                    if (i + 1 < lines.length) console.log('   ' + lines[i + 1].trim());
                    if (i + 2 < lines.length) console.log('   ' + lines[i + 2].trim());
                    found = true;
                    break;
                }
            }

            console.log('');
            console.log('✅ The seed phrase IS stored in the keychain.');
            console.log('✅ The Rust app should be able to retrieve it.');
            console.log('');
            console.log('📋 Next steps:');
            console.log('   1. In the desktop app, look for a "Connect Worker" button');
            console.log('   2. Or go to Settings/Configuration to set endpoint');
            console.log('   3. Endpoint should be: ws://127.0.0.1:9944');
            console.log('   4. Click "Connect" or "Start Worker"');

        } else {
            console.log('❌ Credential NOT FOUND in Windows Credential Manager!');
            console.log('');
            console.log('Expected to find:');
            console.log(`   Target: ${targetName}`);
            console.log('');
            console.log('Available qxchain credentials:');
            const qxchainLines = output.split('\n').filter(line => line.includes('qxchain'));
            if (qxchainLines.length > 0) {
                qxchainLines.forEach(line => console.log('   ' + line.trim()));
            } else {
                console.log('   (none)');
            }
        }

    } catch (error) {
        console.error('❌ Error checking credentials:', error.message);
    }
}

const address = process.argv[2] || '5H65ho969QkfaTGPqSM66pbUDGx2mQXwBU85R78cUZW1rGP8';
testKeychain(address);
