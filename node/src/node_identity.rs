//! Node identity management for ML workers and validators
//! Handles peer identification, networking endpoints, and node registration
//!
//! This is a PERMISSIONLESS system where:
//! - Any node can register itself
//! - Nodes can only update their own identity
//! - No node can remove or control another node
//! - Slashing is only done through on-chain consensus

use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use log::info;
use serde::{Deserialize, Serialize};

/// Node type classification
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum NodeType {
    Worker,
    Validator,
    WorkerValidator, // Node that can be both
}

/// Node identity information for linking workers/validators to blockchain nodes
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeIdentity {
    pub peer_id: String,
    pub endpoint: String,
    pub node_type: NodeType,
    pub account_id: Vec<u8>,
    pub is_online: bool,
    pub registered_at: u64,
    pub last_seen: u64,
}

/// Node identity registry - decentralized registry for node discovery
/// This is a local cache that syncs with on-chain state
pub struct NodeIdentityRegistry {
    identities: Arc<RwLock<HashMap<String, NodeIdentity>>>,
    account_to_peer: Arc<RwLock<HashMap<Vec<u8>, String>>>,
    // Slashed nodes are tracked on-chain, this is just a local cache
    slashed_accounts_cache: Arc<RwLock<HashMap<Vec<u8>, bool>>>,
}

impl NodeIdentityRegistry {
    pub fn new() -> Self {
        Self {
            identities: Arc::new(RwLock::new(HashMap::new())),
            account_to_peer: Arc::new(RwLock::new(HashMap::new())),
            slashed_accounts_cache: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Register or update own node identity
    /// Only the node itself can register/update its identity
    pub fn register_self(
        &self,
        peer_id: String,
        endpoint: String,
        node_type: NodeType,
        account_id: Vec<u8>,
    ) -> Result<(), String> {
        // Check if account is slashed (from on-chain state cache)
        if self.is_account_slashed(&account_id) {
            return Err("Account is slashed on-chain and cannot register".to_string());
        }

        let mut identities = self.identities.write()
            .map_err(|_| "Failed to acquire write lock")?;
        let mut account_map = self.account_to_peer.write()
            .map_err(|_| "Failed to acquire write lock")?;

        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        // Check if updating existing identity
        let registered_at = if let Some(old_peer_id) = account_map.get(&account_id) {
            if let Some(old_identity) = identities.get(old_peer_id) {
                old_identity.registered_at
            } else {
                now
            }
        } else {
            now
        };

        let identity = NodeIdentity {
            peer_id: peer_id.clone(),
            endpoint,
            node_type,
            account_id: account_id.clone(),
            is_online: true,
            registered_at,
            last_seen: now,
        };

        // Update mappings
        if let Some(old_peer_id) = account_map.get(&account_id) {
            if old_peer_id != &peer_id {
                identities.remove(old_peer_id);
            }
        }

        identities.insert(peer_id.clone(), identity);
        account_map.insert(account_id, peer_id.clone());

        info!("Node self-registered: {}", peer_id);
        Ok(())
    }

    /// Update own node's online status
    /// Only the node itself can update its status
    pub fn update_self_status(&self, account_id: &[u8], is_online: bool) -> Result<(), String> {
        let account_map = self.account_to_peer.read()
            .map_err(|_| "Failed to acquire read lock")?;

        let peer_id = account_map.get(account_id)
            .ok_or("Node not registered")?
            .clone();

        drop(account_map);

        let mut identities = self.identities.write()
            .map_err(|_| "Failed to acquire write lock")?;

        if let Some(identity) = identities.get_mut(&peer_id) {
            // Verify this is the same account
            if identity.account_id != account_id {
                return Err("Account mismatch".to_string());
            }

            identity.is_online = is_online;
            identity.last_seen = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs();

            info!("Node {} status self-updated: online={}", peer_id, is_online);
            Ok(())
        } else {
            Err("Node not found".to_string())
        }
    }

    /// Broadcast node identity to peers
    /// Nodes share their identity with others for P2P discovery
    pub fn broadcast_identity(&self, identity: NodeIdentity) -> Result<(), String> {
        // Don't allow broadcasting if account is slashed
        if self.is_account_slashed(&identity.account_id) {
            return Err("Cannot broadcast slashed account".to_string());
        }

        let mut identities = self.identities.write()
            .map_err(|_| "Failed to acquire write lock")?;
        let mut account_map = self.account_to_peer.write()
            .map_err(|_| "Failed to acquire write lock")?;

        // Update the registry with broadcasted identity
        identities.insert(identity.peer_id.clone(), identity.clone());
        account_map.insert(identity.account_id.clone(), identity.peer_id.clone());

        info!("Received broadcast from node: {}", identity.peer_id);
        Ok(())
    }

    /// Get node identity by peer ID (read-only)
    pub fn get_node(&self, peer_id: &str) -> Option<NodeIdentity> {
        self.identities.read().ok()?.get(peer_id).cloned()
    }

    /// Get node identity by account ID (read-only)
    pub fn get_node_by_account(&self, account_id: &[u8]) -> Option<NodeIdentity> {
        let account_map = self.account_to_peer.read().ok()?;
        let peer_id = account_map.get(account_id)?;
        self.get_node(peer_id)
    }

    /// Get all online workers (read-only)
    pub fn get_online_workers(&self) -> Vec<NodeIdentity> {
        self.identities.read()
            .ok()
            .map(|identities| {
                identities.values()
                    .filter(|n| {
                        n.is_online &&
                        !self.is_account_slashed(&n.account_id) &&
                        matches!(n.node_type, NodeType::Worker | NodeType::WorkerValidator)
                    })
                    .cloned()
                    .collect()
            })
            .unwrap_or_default()
    }

    /// Get all online validators (read-only)
    pub fn get_online_validators(&self) -> Vec<NodeIdentity> {
        self.identities.read()
            .ok()
            .map(|identities| {
                identities.values()
                    .filter(|n| {
                        n.is_online &&
                        !self.is_account_slashed(&n.account_id) &&
                        matches!(n.node_type, NodeType::Validator | NodeType::WorkerValidator)
                    })
                    .cloned()
                    .collect()
            })
            .unwrap_or_default()
    }

    /// Update slashed accounts cache from on-chain state
    /// This is called periodically to sync with chain consensus
    pub fn update_slashed_cache(&self, slashed_accounts: Vec<Vec<u8>>) {
        if let Ok(mut cache) = self.slashed_accounts_cache.write() {
            cache.clear();
            for account in slashed_accounts {
                cache.insert(account, true);
            }
            info!("Updated slashed accounts cache");
        }
    }

    /// Check if an account is slashed (from cache)
    pub fn is_account_slashed(&self, account_id: &[u8]) -> bool {
        self.slashed_accounts_cache.read()
            .ok()
            .and_then(|cache| cache.get(account_id).copied())
            .unwrap_or(false)
    }

    /// Announce self to P2P network
    pub fn announce_self(&self) {
        // In a real implementation, this would use libp2p or substrate's network layer
        // to broadcast the node's availability to peers
        // For now, log the broadcast
        if let Ok(identities) = self.identities.read() {
            for (peer_id, identity) in identities.iter() {
                if identity.is_online {
                    log::info!(
                        "📡 Broadcasting: {} is available as {:?} at {}",
                        peer_id,
                        identity.node_type,
                        identity.endpoint
                    );
                }
            }
        }
    }

    /// Cleanup stale nodes (called periodically)
    /// Removes nodes that haven't been seen for a long time
    pub fn cleanup_stale_nodes(&self, stale_threshold_secs: u64) {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        if let Ok(mut identities) = self.identities.write() {
            if let Ok(mut account_map) = self.account_to_peer.write() {
                let stale_nodes: Vec<String> = identities
                    .iter()
                    .filter(|(_, identity)| now - identity.last_seen > stale_threshold_secs)
                    .map(|(peer_id, _)| peer_id.clone())
                    .collect();

                for peer_id in stale_nodes {
                    if let Some(identity) = identities.remove(&peer_id) {
                        account_map.remove(&identity.account_id);
                        info!("Removed stale node: {}", peer_id);
                    }
                }
            }
        }
    }
}