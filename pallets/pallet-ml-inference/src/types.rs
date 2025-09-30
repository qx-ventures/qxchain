//! Common types for ML inference system
//! These types are shared between the pallet and node implementations

use codec::{Decode, Encode};
use frame::prelude::*;
use polkadot_sdk::polkadot_sdk_frame as frame;

/// Inference status tracking
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub enum InferenceStatus {
    Queued,
    Processing,
    Pending,
    Challenged,
    Validated,
    Slashed,
}

/// Request status for tracking
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub enum RequestStatus {
    Queued,
    Assigned,
    Completed,
    Failed,
}

/// Reason for node slashing
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub enum SlashReason {
    WorkerSlashed,
    ValidatorMisbehavior,
    NodeOffline,
}

/// Challenge data for tracking validator challenges
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct Challenge<AccountId> {
    pub validator: AccountId,
    pub expected_output: BoundedVec<u8, ConstU32<4096>>,
    pub submitted_at: u32,
}

/// Inference request data
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct InferenceRequest<AccountId> {
    pub customer: AccountId,
    pub target_worker: AccountId,
    pub prompt: BoundedVec<u8, ConstU32<2048>>,
    pub model_id: u32,
    pub status: RequestStatus,
    pub created_at: u32,
}

/// Inference result data
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct InferenceResult<AccountId> {
    pub request_id: u32,
    pub worker: AccountId,
    pub output: BoundedVec<u8, ConstU32<4096>>,
    pub status: InferenceStatus,
    pub submitted_at: u32,
}