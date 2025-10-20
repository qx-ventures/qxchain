// Allowed since it's actually better to panic during chain setup when there is an error
#![allow(clippy::unwrap_used)]

use super::*;

pub fn mainnet_config() -> Result<ChainSpec, String> {
    let wasm_binary = WASM_BINARY.ok_or("Mainnet wasm not available".to_string())?;

    // Give front-ends necessary data to present to users
    let mut properties = polkadot_sdk::sc_service::Properties::new();
    properties.insert("tokenSymbol".into(), "QX".into());
    properties.insert("tokenDecimals".into(), 12.into());
    properties.insert("ss58Format".into(), 42.into());

    Ok(ChainSpec::builder(
        wasm_binary,
        Extensions {
            bad_blocks: Some(HashSet::new()),
            ..Default::default()
        },
    )
    .with_name("QXChain Mainnet")
    .with_protocol_id("qxchain")
    .with_id("qxchain_mainnet")
    .with_chain_type(ChainType::Live)
    .with_boot_nodes(vec![
        // TODO: Add your mainnet bootnodes here
        // Example format:
        // "/dns/bootnode.qxchain.io/tcp/30333/ws/p2p/<PEER_ID>"
        //     .parse()
        //     .unwrap(),
    ])
    .with_genesis_config_patch(mainnet_genesis(
        // Initial PoA authorities (Validators)
        vec![
            // Validator 1 (qxchain-validator-01) - Also sudo account
            authority_keys_from_ss58(
                "5GyAAHVMUiumNzDxQAYT4uUNPGuufv383MiKyDNkwTndHBog", // Aura
                "5GZmHXcxXBS3gX9kgh8VNkmwGLezjCeb6PiQjkb5irPqq7eU", // Grandpa
            ),
            // Validator 2 (qxchain-validator-02)
            authority_keys_from_ss58(
                "5H6Tf2hamehd3ioXa33zyYWxZriFFdytkUN8kNUu5qjbLYa8", // Aura
                "5Gb4cT7YWKPWN1Bm2ix3n5aLfYBEJHZnT4rxfRLht2uZt2rz", // Grandpa
            ),
            // Validator 3 (qxchain-validator-03)
            authority_keys_from_ss58(
                "5EsSP19v8UXzuAdncoKNuuRmiGdyjDdRBBqecgS77jA54W9Z", // Aura
                "5HLN17LsCZ9jKTSgQb9c5i5Kn7mieTZxfnRpF5mXHqnokriR", // Grandpa
            ),
            // Validator 4 (qxchain-validator-04)
            authority_keys_from_ss58(
                "5CFFugsxfkHK1PQgsd4r7Ge6vtXX6oEdko9nhTUmCKvKti9k", // Aura
                "5EWUwAgL7DMHwrivqUXDq3DZfZ7n22QyW4zSSxr7imakQwtS", // Grandpa
            ),
        ],
        // Sudo account - validator-01
        Ss58Codec::from_ss58check("5GyAAHVMUiumNzDxQAYT4uUNPGuufv383MiKyDNkwTndHBog").unwrap(),
        // Pre-funded accounts for mainnet
        vec![
            // Validator 1 (sudo) - Pre-funded for transaction fees
            (
                Ss58Codec::from_ss58check("5GyAAHVMUiumNzDxQAYT4uUNPGuufv383MiKyDNkwTndHBog").unwrap(),
                1_000_000_000_000_000u128, // 1 million QX tokens
            ),
        ],
    ))
    .with_properties(properties)
    .build())
}

// Configure initial storage state for mainnet
fn mainnet_genesis(
    initial_authorities: Vec<(AuraId, GrandpaId)>,
    root_key: AccountId,
    endowed_accounts: Vec<(AccountId, u128)>,
) -> serde_json::Value {
    serde_json::json!({
        "balances": {
            "balances": endowed_accounts
        },
        "aura": {
            "authorities": initial_authorities.iter().map(|x| x.0.clone()).collect::<Vec<_>>()
        },
        "grandpa": {
            "authorities": initial_authorities
                .iter()
                .map(|x| (x.1.clone(), 1))
                .collect::<Vec<_>>()
        },
        "sudo": {
            "key": Some(root_key)
        },
    })
}
