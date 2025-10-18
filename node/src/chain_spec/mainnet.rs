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
            // Validator 1 (validator-01) - Also sudo account
            authority_keys_from_ss58(
                "5FUK2frew1ogfbMDuHBSwMaga3dEGJp11ZQLjmtxZs7rwcva", // Aura
                "5HHuZ3bbPcadgR5yes42K4JrYMFqygoWLPyfAg4Q5spH6bMH", // Grandpa
            ),
            // Validator 2 (validator-02)
            authority_keys_from_ss58(
                "5D2Wg5PJgksxeARcGcGPR55nshKDZ7xZNpG1g1nY3bkFGgYT", // Aura
                "5H3phgrTxjFcgBbwDUd1HrDcDb3qadfGdBkdHM5gZf9SRRoN", // Grandpa
            ),
            // Validator 3 (validator-03)
            authority_keys_from_ss58(
                "5DyMwhkTjr3W8edx1miE7rTVj3Sg2zwQajemyRnkh6HsSc3J", // Aura
                "5CqsNdzzRKA2kJdgxHx4VZ6MnpneMy6zh9qKJHkZ5reNtzVj", // Grandpa
            ),
            // Validator 4 (validator-04)
            authority_keys_from_ss58(
                "5ELgkJdjkkLQzi8k5giKpEWZhreMJMXBmeKa19B5Fy1gzi44", // Aura
                "5HBxoDQ95gmnUVmeT8XcdHVZ82ZnZMku8TaSaCbHiYpW922b", // Grandpa
            ),
        ],
        // Sudo account - validator-01
        Ss58Codec::from_ss58check("5FUK2frew1ogfbMDuHBSwMaga3dEGJp11ZQLjmtxZs7rwcva").unwrap(),
        // Pre-funded accounts for mainnet
        vec![
            // Validator 1 (sudo) - Pre-funded for transaction fees
            (
                Ss58Codec::from_ss58check("5FUK2frew1ogfbMDuHBSwMaga3dEGJp11ZQLjmtxZs7rwcva").unwrap(),
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
