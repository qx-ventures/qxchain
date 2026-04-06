// Allowed since it's actually better to panic during chain setup when there is an error
#![allow(clippy::unwrap_used)]

use super::*;

pub fn localnet_config(single_authority: bool) -> Result<ChainSpec, String> {
    let wasm_binary = WASM_BINARY.ok_or("Development wasm not available".to_string())?;

    // Give front-ends necessary data to present to users
    let mut properties = polkadot_sdk::sc_service::Properties::new();
    properties.insert("tokenSymbol".into(), "QX".into());
    properties.insert("tokenDecimals".into(), 12.into());
    properties.insert("ss58Format".into(), 42.into());

    Ok(ChainSpec::builder(
        wasm_binary,
        Extensions {
            bad_blocks: Some(HashSet::from_iter(vec![
                // Example bad block - you can remove this in production
                H256::from_str(
                    "0x0000000000000000000000000000000000000000000000000000000000000000",
                )
                .unwrap(),
            ])),
            ..Default::default()
        },
    )
    .with_name("QXChain Local")
    .with_protocol_id("qxchain")
    .with_id("qxchain_local")
    .with_chain_type(ChainType::Local)
    .with_genesis_config_patch(localnet_genesis(
        // Initial PoA authorities (Validators)
        // aura | grandpa
        if single_authority {
            // single authority allows you to run the network using a single node
            vec![authority_keys_from_seed("Alice")]
        } else {
            vec![
                authority_keys_from_seed("Alice"),
                authority_keys_from_seed("Bob"),
            ]
        },
        // Pre-funded accounts
        true,
    ))
    .with_properties(properties)
    .build())
}

fn localnet_genesis(
    initial_authorities: Vec<(AuraId, GrandpaId)>,
    _enable_println: bool,
) -> serde_json::Value {
    let balances = vec![
        (
            get_account_id_from_seed::<sr25519::Public>("Alice"),
            1_000_000_000_000_000u128,
        ),
        (
            get_account_id_from_seed::<sr25519::Public>("Bob"),
            1_000_000_000_000_000u128,
        ),
        (
            get_account_id_from_seed::<sr25519::Public>("Charlie"),
            1_000_000_000_000_000u128,
        ),
        (
            get_account_id_from_seed::<sr25519::Public>("Dave"),
            2_000_000_000_000u128,
        ),
        (
            get_account_id_from_seed::<sr25519::Public>("Eve"),
            2_000_000_000_000u128,
        ),
        (
            get_account_id_from_seed::<sr25519::Public>("Ferdie"),
            2_000_000_000_000u128,
        ),
        // Faucet pot - 1 million QX for user onboarding
        (
            faucet_pot_account(),
            1_000_000_000_000_000_000u128, // 1 million QX tokens
        ),
    ];

    serde_json::json!({
        "balances": { "balances": balances },
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
            "key": Some(get_account_id_from_seed::<sr25519::Public>("Alice"))
        },
    })
}
