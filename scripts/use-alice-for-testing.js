#!/usr/bin/env node
/**
 * Quick test - fund Alice's account so we can use //Alice for testing
 */

const { ApiPromise, WsProvider, Keyring } = require('@polkadot/api');

async function main() {
    console.log('\n🧪 Quick Fix: Use Alice for Local Testing\n');
    console.log('='.repeat(70));

    // Alice's address
    const aliceAddress = '5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY';

    console.log('\n📝 To bypass the keychain issue:');
    console.log('\n1. In the desktop app, when creating/recovering identity:');
    console.log('   Use seed phrase: //Alice');
    console.log('   This will generate Alice\'s account');
    console.log('');
    console.log('2. Alice already has tokens on the local chain');
    console.log('');
    console.log('3. This works because //Alice is built into the keyring library');
    console.log('   It doesn\'t require Windows Credential Manager');
    console.log('');
    console.log('Alice\'s address:', aliceAddress);

    // Check Alice's balance
    console.log('\nChecking Alice\'s current balance...');
    const provider = new WsProvider('ws://127.0.0.1:9944');
    const api = await ApiPromise.create({ provider });

    const account = await api.query.system.account(aliceAddress);
    const balance = account.data.free.toBigInt();

    console.log(`✅ Alice has: ${balance.toString()} plancks`);
    console.log(`   (${(Number(balance) / 1e12).toFixed(4)} tokens)`);
    console.log('');
    console.log('✅ Ready for testing!');

    await api.disconnect();
}

main().catch(console.error);
