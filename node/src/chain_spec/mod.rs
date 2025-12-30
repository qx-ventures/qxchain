// Allowed since it's actually better to panic during chain setup when there is an error
#![allow(clippy::unwrap_used)]

pub mod mainnet;
pub mod localnet;

use qxchain_runtime::{Block, WASM_BINARY};
use polkadot_sdk::{
    sc_chain_spec::ChainSpecExtension,
    sc_service::ChainType,
    sp_consensus_aura::sr25519::AuthorityId as AuraId,
    sp_consensus_grandpa::AuthorityId as GrandpaId,
    sp_core::crypto::Ss58Codec,
    sp_core::{H256, Pair, Public, sr25519},
    sp_runtime::{AccountId32, traits::{IdentifyAccount, Verify}},
};
use std::collections::HashSet;
use std::str::FromStr;
use serde::{Deserialize, Serialize};

pub type AccountId = AccountId32;
pub type Signature = polkadot_sdk::sp_runtime::MultiSignature;

/// Node `ChainSpec` extensions.
#[derive(Default, Clone, Serialize, Deserialize, ChainSpecExtension)]
#[serde(rename_all = "camelCase")]
pub struct Extensions {
    /// Block numbers with known hashes.
    pub fork_blocks: polkadot_sdk::sc_client_api::ForkBlocks<Block>,
    /// Known bad block hashes.
    pub bad_blocks: polkadot_sdk::sc_client_api::BadBlocks<Block>,
}

/// Specialized `ChainSpec`. This is a specialization of the general Substrate ChainSpec type.
pub type ChainSpec = polkadot_sdk::sc_service::GenericChainSpec<Extensions>;

/// Generate a crypto pair from seed.
pub fn get_from_seed<TPublic: Public>(seed: &str) -> <TPublic::Pair as Pair>::Public {
    TPublic::Pair::from_string(&format!("//{seed}"), None)
        .expect("static values are valid; qed")
        .public()
}

type AccountPublic = <Signature as Verify>::Signer;

/// Generate an account ID from seed.
pub fn get_account_id_from_seed<TPublic: Public>(seed: &str) -> AccountId
where
    AccountPublic: From<<TPublic::Pair as Pair>::Public>,
{
    AccountPublic::from(get_from_seed::<TPublic>(seed)).into_account()
}

/// Generate an Aura authority key from seed.
pub fn authority_keys_from_seed(s: &str) -> (AuraId, GrandpaId) {
    (get_from_seed::<AuraId>(s), get_from_seed::<GrandpaId>(s))
}

/// Generate authority keys from SS58 addresses.
pub fn authority_keys_from_ss58(s_aura: &str, s_grandpa: &str) -> (AuraId, GrandpaId) {
    (
        get_aura_from_ss58_addr(s_aura),
        get_grandpa_from_ss58_addr(s_grandpa),
    )
}

pub fn get_aura_from_ss58_addr(s: &str) -> AuraId {
    Ss58Codec::from_ss58check(s).unwrap()
}

pub fn get_grandpa_from_ss58_addr(s: &str) -> GrandpaId {
    Ss58Codec::from_ss58check(s).unwrap()
}

/// Get the faucet pot account (must match runtime FaucetPotAccount)
pub fn faucet_pot_account() -> AccountId {
    AccountId32::new([
        0x71, 0x78, 0x2f, 0x66, 0x61, 0x75, 0x63, 0x65, // "qx/fauce"
        0x74, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // "t" + padding
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ])
}
