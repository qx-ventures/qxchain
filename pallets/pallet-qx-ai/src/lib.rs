//! QX AI pallet - AI inference verification with Proof of Logits
//!
//! This pallet implements the application layer for QX Chain's civic AI infrastructure.
//! AIWorkers and AIValidators are NOT blockchain consensus nodes - they are application-layer
//! entities that interact with the chain to provide and verify AI services.
//!
//! AIWorkers: Civic entities that run off-chain AI inference and submit cryptographic proofs
//! AIValidators: Reputation-weighted validators that verify submissions by checking a single random checkpoint
//!
//! Validation Approach:
//! - Validators are randomly selected weighted by reputation score
//! - Each validator checks ONE random checkpoint for efficient validation
//! - Consensus determined by reputation-weighted voting
//! - Retrospective slashing for both dishonest workers AND validators

#![cfg_attr(not(feature = "std"), no_std)]

extern crate alloc;
use alloc::vec::Vec;

use frame::prelude::*;
use polkadot_sdk::polkadot_sdk_frame as frame;

// Import necessary traits and types
use frame::traits::{Currency, ReservableCurrency, Get};

// Re-export all pallet parts, this is needed to properly import the pallet into the runtime.
pub use pallet::*;

/// Logit checkpoint - hash of logits at specific token position
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo)]
pub struct LogitCheckpoint {
	pub token_index: u32,
	pub logit_hash: BoundedVec<u8, ConstU32<64>>,  // SHA256 hash of logits
	pub token_id: u32,  // Token generated at this position
}

/// Inference proof containing logit hashes
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo)]
pub struct InferenceProof {
	pub checkpoints: BoundedVec<LogitCheckpoint, ConstU32<1000>>,  // All token logit hashes
	pub total_tokens: u32,
}

/// Allowed model metadata
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
#[codec(mel_bound())]
#[cfg_attr(feature = "std", derive(serde::Serialize, serde::Deserialize))]
pub struct AllowedModel {
	pub model_name: BoundedVec<u8, ConstU32<128>>,  // e.g. "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
	pub model_hash: BoundedVec<u8, ConstU32<64>>,   // Hash of model weights
	pub active: bool,
}

/// Inference status tracking (optimistic execution)
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub enum InferenceStatus {
	Pending,      // Available for use, validation in progress (optimistic)
	Challenged,   // Mismatch found, consensus pending
	Finalized,    // Consensus reached, validated as correct
	Slashed,      // Consensus reached, worker was dishonest
}

/// Request status for tracking
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub enum RequestStatus {
	Queued,
	Assigned,
	Completed,
	Failed,
}

/// Validation data for tracking validator verification (single checkpoint)
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct Challenge<AccountId, Balance> {
	pub validator: AccountId,
	pub mismatch_found: bool,  // True if checkpoint failed verification
	pub submitted_at: u32,
	pub stake: Balance, // Validator stake weight for consensus calculation
}

/// Inference request data
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct InferenceRequest<AccountId> {
	pub customer: AccountId,
	pub target_worker: AccountId,
	pub prompt: BoundedVec<u8, ConstU32<2048>>,
	pub model_id: u32,
	pub max_tokens: u32,  // Maximum number of tokens to generate
	pub status: RequestStatus,
	pub created_at: u32,
}

/// Inference result data with cryptographic proof
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct InferenceResult<AccountId> {
	pub request_id: u32,
	pub worker: AccountId,
	pub output: BoundedVec<u8, ConstU32<4096>>,
	pub model_id: u32,  // Which allowed model was used
	pub proof_data: BoundedVec<u8, ConstU32<102400>>,  // Encoded proof (100KB max)
	pub status: InferenceStatus,
	pub submitted_at: u32,
	pub validation_deadline: u32, // Block number when validation window ends
}

#[frame::pallet]
pub mod pallet {
	use super::*;

	#[pallet::config]
	pub trait Config: polkadot_sdk::frame_system::Config {
		type RuntimeEvent: From<Event<Self>> + IsType<<Self as polkadot_sdk::frame_system::Config>::RuntimeEvent>;

		/// The currency trait for handling token operations
		type Currency: Currency<Self::AccountId> + ReservableCurrency<Self::AccountId>;

		/// Minimum stake required for AIWorkers
		#[pallet::constant]
		type MinAIWorkerStake: Get<<Self::Currency as Currency<Self::AccountId>>::Balance>;

		/// Minimum stake required for AIValidators
		#[pallet::constant]
		type MinChallengeStake: Get<<Self::Currency as Currency<Self::AccountId>>::Balance>;

		/// Challenge period in blocks
		#[pallet::constant]
		type ChallengePeriod: Get<BlockNumberFor<Self>>;

		/// Percentage of validator stake needed to slash (51% = 51)
		#[pallet::constant]
		type SlashThreshold: Get<u32>;

		/// Maximum requests in queue per AIWorker
		#[pallet::constant]
		type MaxQueueSize: Get<u32>;
	}

	#[pallet::pallet]
	pub struct Pallet<T>(_);

	/// AIWorkers registered on the network (application layer entities, NOT consensus nodes)
	#[pallet::storage]
	pub type AIWorkers<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, <T::Currency as Currency<T::AccountId>>::Balance>;

	/// AIValidators registered on the network (application layer entities, NOT consensus nodes)
	#[pallet::storage]
	pub type AIValidators<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, <T::Currency as Currency<T::AccountId>>::Balance>;

	/// Validator reputation - accumulated score from successful validations
	#[pallet::storage]
	pub type ValidatorReputation<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, u128, ValueQuery>;

	/// Validator assignments for each inference - validators randomly selected to validate
	#[pallet::storage]
	pub type InferenceValidatorAssignments<T: Config> = StorageMap<_, Blake2_128Concat, u32, BoundedVec<T::AccountId, ConstU32<10>>>;

	/// Allowed models registry
	#[pallet::storage]
	pub type AllowedModels<T: Config> = StorageMap<_, Blake2_128Concat, u32, AllowedModel>;

	/// Next model ID counter
	#[pallet::storage]
	pub type NextModelId<T: Config> = StorageValue<_, u32, ValueQuery>;

	/// Next request ID
	#[pallet::storage]
	pub type NextRequestId<T: Config> = StorageValue<_, u32, ValueQuery>;

	/// Next inference ID
	#[pallet::storage]
	pub type NextInferenceId<T: Config> = StorageValue<_, u32, ValueQuery>;

	/// Inference requests in queue
	#[pallet::storage]
	pub type InferenceRequests<T: Config> = StorageMap<_, Blake2_128Concat, u32, InferenceRequest<T::AccountId>>;

	/// Inference results with proofs
	#[pallet::storage]
	pub type InferenceResults<T: Config> = StorageMap<_, Blake2_128Concat, u32, InferenceResult<T::AccountId>>;

	/// AIWorker queues - maps AIWorker to list of request IDs
	#[pallet::storage]
	pub type AIWorkerQueues<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, BoundedVec<u32, T::MaxQueueSize>>;

	/// Request to AIWorker mapping
	#[pallet::storage]
	pub type RequestWorkerMap<T: Config> = StorageMap<_, Blake2_128Concat, u32, T::AccountId>;

	/// AIWorker status - true if online/available
	#[pallet::storage]
	pub type AIWorkerStatus<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, bool>;

	/// Challenges for each inference - validators' checkpoint verification results
	#[pallet::storage]
	pub type InferenceChallenges<T: Config> = StorageMap<_, Blake2_128Concat, u32, BoundedVec<Challenge<T::AccountId, <T::Currency as Currency<T::AccountId>>::Balance>, ConstU32<100>>>;

	/// Banned AIWorkers - workers that have been slashed and removed from network
	#[pallet::storage]
	pub type BannedAIWorkers<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, bool>;

	/// Events emitted by the pallet
	#[pallet::event]
	#[pallet::generate_deposit(pub(super) fn deposit_event)]
	pub enum Event<T: Config> {
		/// AIWorker registered (application layer entity, not a consensus node)
		AIWorkerRegistered { who: T::AccountId, stake: <T::Currency as Currency<T::AccountId>>::Balance },
		/// AIValidator registered (application layer entity, not a consensus node)
		AIValidatorRegistered { who: T::AccountId, stake: <T::Currency as Currency<T::AccountId>>::Balance },
		/// Request submitted to queue
		RequestSubmitted { request_id: u32, customer: T::AccountId, model_id: u32 },
		/// Request assigned to AIWorker
		RequestAssigned { request_id: u32, worker: T::AccountId },
		/// Inference submitted with cryptographic proof (results available immediately)
		InferenceSubmitted { inference_id: u32, request_id: u32, worker: T::AccountId, total_tokens: u32, validation_deadline: u32 },
		/// Inference validated successfully by validator (single checkpoint)
		InferenceValidated { inference_id: u32, validator: T::AccountId },
		/// Inference challenged (mismatch found in single checkpoint)
		InferenceChallenged { inference_id: u32, validator: T::AccountId },
		/// Inference automatically finalized after challenge period
		InferenceFinalized { inference_id: u32, worker: T::AccountId },
		/// AIWorker slashed after validation failure
		AIWorkerSlashed { worker: T::AccountId, inference_id: u32, amount: <T::Currency as Currency<T::AccountId>>::Balance },
		/// AIWorker banned from network
		AIWorkerBanned { worker: T::AccountId, inference_id: u32 },
		/// Challenge consensus reached (51%+ validators agree)
		ChallengeConsensusReached { inference_id: u32, challenge_stake_weight: u128, total_validator_stake: u128 },
		/// AIWorker status updated
		AIWorkerStatusUpdated { worker: T::AccountId, online: bool },
		/// Request completed
		RequestCompleted { request_id: u32, inference_id: u32 },
		/// Model added to allowed registry
		ModelAdded { model_id: u32, model_name: BoundedVec<u8, ConstU32<128>> },
		/// Validators assigned to inference
		ValidatorsAssigned { inference_id: u32, validators: BoundedVec<T::AccountId, ConstU32<10>> },
		/// Validator reputation rewarded for correct validation
		ValidatorRewarded { validator: T::AccountId, amount: u128, new_reputation: u128 },
		/// Validator slashed for incorrect validation (retrospective slashing)
		ValidatorSlashed { validator: T::AccountId, reputation_slashed: u128, stake_slashed: <T::Currency as Currency<T::AccountId>>::Balance, new_reputation: u128 },
	}

	/// Errors that can be returned by this pallet
	#[pallet::error]
	pub enum Error<T> {
		/// AIWorker already registered
		AIWorkerAlreadyRegistered,
		/// AIValidator already registered
		AIValidatorAlreadyRegistered,
		/// AIWorker not found
		AIWorkerNotFound,
		/// AIValidator not found
		AIValidatorNotFound,
		/// Inference not found
		InferenceNotFound,
		/// Request not found
		RequestNotFound,
		/// Insufficient stake
		InsufficientStake,
		/// Challenge period expired
		ChallengePeriodExpired,
		/// Already validated this inference
		AlreadyValidated,
		/// Cannot validate own inference
		CannotValidateSelf,
		/// Inference not in pending status
		InferenceNotPending,
		/// Invalid model ID
		InvalidModel,
		/// Model not active
		ModelNotActive,
		/// AIWorker queue full
		AIWorkerQueueFull,
		/// Request already assigned
		RequestAlreadyAssigned,
		/// Request not assigned to this AIWorker
		RequestNotAssigned,
		/// AIWorker is banned
		AIWorkerBanned,
		/// Invalid proof structure
		InvalidProofStructure,
		/// Invalid checkpoint index
		InvalidCheckpointIndex,
		/// Not assigned to validate this inference
		NotAssignedValidator,
		/// No validators available for selection
		NoValidatorsAvailable,
	}

	#[pallet::call]
	impl<T: Config> Pallet<T> {
		/// Register as an AIWorker with stake (application layer entity, not a consensus node)
		#[pallet::call_index(0)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn register_ai_worker(
			origin: OriginFor<T>,
			stake: <T::Currency as Currency<T::AccountId>>::Balance,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			ensure!(!AIWorkers::<T>::contains_key(&who), Error::<T>::AIWorkerAlreadyRegistered);
			ensure!(!BannedAIWorkers::<T>::contains_key(&who), Error::<T>::AIWorkerBanned);
			ensure!(stake >= T::MinAIWorkerStake::get(), Error::<T>::InsufficientStake);

			T::Currency::reserve(&who, stake)?;

			AIWorkers::<T>::insert(&who, stake);
			AIWorkerQueues::<T>::insert(&who, BoundedVec::new());
			AIWorkerStatus::<T>::insert(&who, false);

			Self::deposit_event(Event::AIWorkerRegistered { who, stake });
			Ok(())
		}

		/// Register as an AIValidator with stake (application layer entity, not a consensus node)
		#[pallet::call_index(1)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn register_ai_validator(
			origin: OriginFor<T>,
			stake: <T::Currency as Currency<T::AccountId>>::Balance,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			ensure!(!AIValidators::<T>::contains_key(&who), Error::<T>::AIValidatorAlreadyRegistered);
			ensure!(stake >= T::MinChallengeStake::get(), Error::<T>::InsufficientStake);

			T::Currency::reserve(&who, stake)?;

			AIValidators::<T>::insert(&who, stake);
			// Initialize validator reputation to 100 (baseline for new validators)
			ValidatorReputation::<T>::insert(&who, 100u128);

			Self::deposit_event(Event::AIValidatorRegistered { who, stake });
			Ok(())
		}

		/// Submit an inference request to a specific AIWorker
		#[pallet::call_index(2)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn submit_request(
			origin: OriginFor<T>,
			target_worker: T::AccountId,
			prompt: BoundedVec<u8, ConstU32<2048>>,
			model_id: u32,
			max_tokens: u32,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			ensure!(AIWorkers::<T>::contains_key(&target_worker), Error::<T>::AIWorkerNotFound);
			ensure!(!BannedAIWorkers::<T>::contains_key(&target_worker), Error::<T>::AIWorkerBanned);

			let model = AllowedModels::<T>::get(model_id).ok_or(Error::<T>::InvalidModel)?;
			ensure!(model.active, Error::<T>::ModelNotActive);

			let bounded_prompt = prompt;

			let request_id = NextRequestId::<T>::get();
			NextRequestId::<T>::put(request_id + 1);

			let current_block = frame_system::Pallet::<T>::block_number();
			let block_number: u32 = current_block.saturated_into();

			let request = InferenceRequest {
				customer: who.clone(),
				target_worker: target_worker.clone(),
				prompt: bounded_prompt,
				model_id,
				max_tokens,
				status: RequestStatus::Queued,
				created_at: block_number,
			};

			InferenceRequests::<T>::insert(&request_id, &request);
			RequestWorkerMap::<T>::insert(&request_id, &target_worker);

			AIWorkerQueues::<T>::try_mutate(&target_worker, |queue_opt| {
				let queue = queue_opt.as_mut().ok_or(Error::<T>::AIWorkerNotFound)?;
				queue.try_push(request_id).map_err(|_| Error::<T>::AIWorkerQueueFull)?;
				Ok::<(), Error<T>>(())
			})?;

			Self::deposit_event(Event::RequestSubmitted {
				request_id,
				customer: who,
				model_id
			});
			Self::deposit_event(Event::RequestAssigned {
				request_id,
				worker: target_worker
			});

			Ok(())
		}

		/// Update AIWorker online status
		#[pallet::call_index(3)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn update_ai_worker_status(
			origin: OriginFor<T>,
			online: bool,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			ensure!(AIWorkers::<T>::contains_key(&who), Error::<T>::AIWorkerNotFound);

			AIWorkerStatus::<T>::insert(&who, online);

			Self::deposit_event(Event::AIWorkerStatusUpdated {
				worker: who,
				online
			});

			Ok(())
		}

		/// Submit inference result with cryptographic proof
		#[pallet::call_index(4)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn submit_inference(
			origin: OriginFor<T>,
			request_id: u32,
			output: BoundedVec<u8, ConstU32<4096>>,
			model_id: u32,
			proof_data: BoundedVec<u8, ConstU32<102400>>,  // Encoded proof (100KB max)
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			ensure!(AIWorkers::<T>::contains_key(&who), Error::<T>::AIWorkerNotFound);
			ensure!(!BannedAIWorkers::<T>::contains_key(&who), Error::<T>::AIWorkerBanned);

			let model = AllowedModels::<T>::get(model_id).ok_or(Error::<T>::InvalidModel)?;
			ensure!(model.active, Error::<T>::ModelNotActive);

			let request = InferenceRequests::<T>::get(&request_id)
				.ok_or(Error::<T>::RequestNotFound)?;

				ensure!(request.target_worker == who, Error::<T>::RequestNotAssigned);
			ensure!(request.status == RequestStatus::Queued, Error::<T>::RequestAlreadyAssigned);
			ensure!(request.model_id == model_id, Error::<T>::InvalidModel);

			// Decode proof from bytes
			let proof = InferenceProof::decode(&mut &proof_data[..])
				.map_err(|_| Error::<T>::InvalidProofStructure)?;

			// Validate proof structure
			ensure!(
				proof.checkpoints.len() as u32 == proof.total_tokens,
				Error::<T>::InvalidProofStructure
			);

			// Capture total_tokens before moving proof
			let total_tokens = proof.total_tokens;

			let bounded_output = output;

			let inference_id = NextInferenceId::<T>::get();
			NextInferenceId::<T>::put(inference_id + 1);

			let current_block = frame_system::Pallet::<T>::block_number();
			let block_number: u32 = current_block.saturated_into();

			let validation_period: u32 = T::ChallengePeriod::get().saturated_into();
			let validation_deadline = block_number.saturating_add(validation_period);

			let result = InferenceResult {
				request_id,
				worker: who.clone(),
				output: bounded_output,
				model_id,
				proof_data,  // Store as bytes
				status: InferenceStatus::Pending,
				submitted_at: block_number,
				validation_deadline,
			};

			InferenceResults::<T>::insert(&inference_id, &result);

			// Select validators for this inference (weighted random selection)
			let selected_validators = Self::select_validators_for_inference(inference_id, 3)?;
			InferenceValidatorAssignments::<T>::insert(inference_id, selected_validators.clone());

			InferenceRequests::<T>::try_mutate(&request_id, |req_opt| {
				let req = req_opt.as_mut().ok_or(Error::<T>::RequestNotFound)?;
				req.status = RequestStatus::Completed;
				Ok::<(), Error<T>>(())
			})?;

			AIWorkerQueues::<T>::try_mutate(&who, |queue_opt| {
				let queue = queue_opt.as_mut().ok_or(Error::<T>::AIWorkerNotFound)?;
				queue.retain(|&id| id != request_id);
				Ok::<(), Error<T>>(())
			})?;

			Self::deposit_event(Event::InferenceSubmitted {
				inference_id,
				request_id,
				worker: who,
				total_tokens,
				validation_deadline,
			});
			Self::deposit_event(Event::ValidatorsAssigned {
				inference_id,
				validators: selected_validators,
			});
			Self::deposit_event(Event::RequestCompleted {
				request_id,
				inference_id
			});

			Ok(())
		}

		/// Submit validation for inference by verifying a single checkpoint (Ambient-style)
		#[pallet::call_index(5)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn submit_validation(
			origin: OriginFor<T>,
			inference_id: u32,
			checkpoint_index: u32,
			computed_hash: [u8; 32],  // SHA256 hash (fixed 32 bytes)
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			let validator_stake = AIValidators::<T>::get(&who)
				.ok_or(Error::<T>::AIValidatorNotFound)?;

			// Check if this validator is assigned to this inference
			let assigned_validators = InferenceValidatorAssignments::<T>::get(inference_id)
				.ok_or(Error::<T>::NotAssignedValidator)?;
			ensure!(assigned_validators.contains(&who), Error::<T>::NotAssignedValidator);

			let inference = InferenceResults::<T>::get(&inference_id)
				.ok_or(Error::<T>::InferenceNotFound)?;

			ensure!(inference.status == InferenceStatus::Pending || inference.status == InferenceStatus::Challenged, Error::<T>::InferenceNotPending);
			ensure!(inference.worker != who, Error::<T>::CannotValidateSelf);

			let current_block = frame_system::Pallet::<T>::block_number();
			let block_number: u32 = current_block.saturated_into();

			ensure!(block_number <= inference.validation_deadline, Error::<T>::ChallengePeriodExpired);

			if let Some(existing_challenges) = InferenceChallenges::<T>::get(&inference_id) {
				ensure!(!existing_challenges.iter().any(|c| c.validator == who), Error::<T>::AlreadyValidated);
			}

			// Decode proof from stored bytes
			let proof = InferenceProof::decode(&mut &inference.proof_data[..])
				.map_err(|_| Error::<T>::InvalidProofStructure)?;

			ensure!(checkpoint_index < proof.total_tokens, Error::<T>::InvalidCheckpointIndex);

			// Verify single checkpoint
			let worker_checkpoint = proof.checkpoints.get(checkpoint_index as usize)
				.ok_or(Error::<T>::InvalidCheckpointIndex)?;

			let mismatch_found = worker_checkpoint.logit_hash.as_slice() != &computed_hash[..];

			let challenge = Challenge {
				validator: who.clone(),
				mismatch_found,
				submitted_at: block_number,
				stake: validator_stake,
			};

			InferenceChallenges::<T>::try_mutate(&inference_id, |challenges_opt| {
				let challenges = challenges_opt.get_or_insert_with(|| BoundedVec::new());
				challenges.try_push(challenge).map_err(|_| Error::<T>::AIWorkerQueueFull)?;
				Ok::<(), Error<T>>(())
			})?;

			if mismatch_found {
				InferenceResults::<T>::try_mutate(&inference_id, |result_opt| {
					let result = result_opt.as_mut().ok_or(Error::<T>::InferenceNotFound)?;
					result.status = InferenceStatus::Challenged;
					Ok::<(), Error<T>>(())
				})?;

				Self::deposit_event(Event::InferenceChallenged {
					inference_id,
					validator: who,
				});
			} else {
				Self::deposit_event(Event::InferenceValidated {
					inference_id,
					validator: who,
				});
			}

			// Check consensus after each validation submission
			Self::check_validator_consensus(inference_id)?;

			Ok(())
		}

		/// Add an allowed model (requires root/sudo)
		#[pallet::call_index(6)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn add_allowed_model(
			origin: OriginFor<T>,
			model_id: u32,
			model_name: BoundedVec<u8, ConstU32<128>>,
			model_hash: BoundedVec<u8, ConstU32<64>>,
		) -> DispatchResult {
			ensure_root(origin)?;

			let model = AllowedModel {
				model_name: model_name.clone(),
				model_hash,
				active: true,
			};

			AllowedModels::<T>::insert(model_id, model);

			Self::deposit_event(Event::ModelAdded { model_id, model_name });

			Ok(())
		}
	}

	impl<T: Config> Pallet<T> {
		/// Select validators for an inference using weighted random selection
		fn select_validators_for_inference(inference_id: u32, num_validators: u32) -> Result<BoundedVec<T::AccountId, ConstU32<10>>, Error<T>> {
			// Collect all validators with their reputation scores
			let mut validators_with_reputation: Vec<(T::AccountId, u128)> = Vec::new();

			for (validator, _stake) in AIValidators::<T>::iter() {
				let reputation = ValidatorReputation::<T>::get(&validator);
				if reputation > 0 {
					validators_with_reputation.push((validator, reputation));
				}
			}

			ensure!(!validators_with_reputation.is_empty(), Error::<T>::NoValidatorsAvailable);

			// Calculate total reputation for weighted selection
			let total_reputation: u128 = validators_with_reputation.iter()
				.map(|(_, rep)| *rep)
				.sum();

			let mut selected = BoundedVec::new();
			let num_to_select = core::cmp::min(num_validators as usize, validators_with_reputation.len());

			// Simple weighted random selection using inference_id as seed
			// In production, use VRF or on-chain randomness
			let mut seed = inference_id as u128;

			for _ in 0..num_to_select {
				if validators_with_reputation.is_empty() {
					break;
				}

				// Generate pseudo-random number based on seed
				seed = seed.wrapping_mul(1103515245).wrapping_add(12345);
				let random_value = (seed / 65536) % total_reputation;

				// Select validator based on weighted probability
				let mut cumulative = 0u128;
				let mut selected_idx = 0;

				for (idx, (_, reputation)) in validators_with_reputation.iter().enumerate() {
					cumulative += *reputation;
					if random_value < cumulative {
						selected_idx = idx;
						break;
					}
				}

				let (validator, _) = validators_with_reputation.remove(selected_idx);
				let _ = selected.try_push(validator);
			}

			Ok(selected)
		}

		/// Reward validator reputation for correct validation
		fn reward_validator_reputation(validator: &T::AccountId, amount: u128) {
			ValidatorReputation::<T>::mutate(validator, |reputation| {
				*reputation = reputation.saturating_add(amount);
			});

			let new_reputation = ValidatorReputation::<T>::get(validator);
			Self::deposit_event(Event::ValidatorRewarded {
				validator: validator.clone(),
				amount,
				new_reputation,
			});
		}

		/// Slash validator reputation and stake for incorrect validation
		fn slash_validator_reputation(validator: &T::AccountId, reputation_amount: u128) -> DispatchResult {
			let validator_stake = AIValidators::<T>::get(validator)
				.ok_or(Error::<T>::AIValidatorNotFound)?;

			// Slash reputation
			ValidatorReputation::<T>::mutate(validator, |reputation| {
				*reputation = reputation.saturating_sub(reputation_amount);
			});

			// Also slash 50% of validator stake as punishment
			let stake_to_slash = validator_stake / 2u32.into();
			let _ = T::Currency::slash_reserved(validator, stake_to_slash);

			let new_reputation = ValidatorReputation::<T>::get(validator);
			Self::deposit_event(Event::ValidatorSlashed {
				validator: validator.clone(),
				reputation_slashed: reputation_amount,
				stake_slashed: stake_to_slash,
				new_reputation,
			});

			Ok(())
		}

		/// Check validator consensus using reputation-weighted voting with retrospective slashing
		/// Auto-triggers when all assigned validators submit (Ambient-style)
		fn check_validator_consensus(inference_id: u32) -> DispatchResult {
			let challenges = InferenceChallenges::<T>::get(&inference_id)
				.unwrap_or_default();

			// Check if all assigned validators have submitted
			let assigned_validators = InferenceValidatorAssignments::<T>::get(inference_id)
				.unwrap_or_default();

			// Only proceed with consensus if all assigned validators have submitted
			if challenges.len() < assigned_validators.len() {
				// Not all validators have submitted yet, wait for more
				return Ok(());
			}

			// All validators have submitted - calculate reputation-weighted votes
			let mut valid_reputation: u128 = 0;
			let mut invalid_reputation: u128 = 0;

			for challenge in &challenges {
				let validator_reputation = ValidatorReputation::<T>::get(&challenge.validator);

				if challenge.mismatch_found {
					invalid_reputation = invalid_reputation.saturating_add(validator_reputation);
				} else {
					valid_reputation = valid_reputation.saturating_add(validator_reputation);
				}
			}

			// Determine consensus based on reputation-weighted voting
			if invalid_reputation > valid_reputation {
				// Majority found mismatch - slash worker and reward/slash validators
				Self::deposit_event(Event::ChallengeConsensusReached {
					inference_id,
					challenge_stake_weight: invalid_reputation,
					total_validator_stake: valid_reputation + invalid_reputation,
				});

				Self::slash_and_ban_ai_worker(inference_id)?;

				// Reward validators who found mismatch, slash those who didn't
				for challenge in &challenges {
					if challenge.mismatch_found {
						Self::reward_validator_reputation(&challenge.validator, 100);
					} else {
						let _ = Self::slash_validator_reputation(&challenge.validator, 50);
					}
				}
			} else {
				// Majority validated correctly - finalize inference and reward/slash validators
				InferenceResults::<T>::try_mutate(&inference_id, |result_opt| {
					if let Some(result) = result_opt {
						result.status = InferenceStatus::Finalized;
					}
					Ok::<(), Error<T>>(())
				})?;

				// Emit finalized event
				if let Some(inference) = InferenceResults::<T>::get(&inference_id) {
					Self::deposit_event(Event::InferenceFinalized {
						inference_id,
						worker: inference.worker.clone(),
					});
				}

				// Reward correct validators, slash dishonest ones
				for challenge in &challenges {
					if !challenge.mismatch_found {
						Self::reward_validator_reputation(&challenge.validator, 100);
					} else {
						let _ = Self::slash_validator_reputation(&challenge.validator, 50);
					}
				}
			}

			Ok(())
		}

		/// Slash AIWorker stake and ban them from the network
		fn slash_and_ban_ai_worker(inference_id: u32) -> DispatchResult {
			let inference = InferenceResults::<T>::get(&inference_id)
				.ok_or(Error::<T>::InferenceNotFound)?;

			let worker = &inference.worker;
			let stake = AIWorkers::<T>::get(worker)
				.ok_or(Error::<T>::AIWorkerNotFound)?;

			let _ = T::Currency::slash_reserved(worker, stake);

			BannedAIWorkers::<T>::insert(worker, true);
			AIWorkers::<T>::remove(worker);
			AIWorkerQueues::<T>::remove(worker);
			AIWorkerStatus::<T>::remove(worker);

			InferenceResults::<T>::try_mutate(&inference_id, |result_opt| {
				let result = result_opt.as_mut().ok_or(Error::<T>::InferenceNotFound)?;
				result.status = InferenceStatus::Slashed;
				Ok::<(), Error<T>>(())
			})?;

			Self::deposit_event(Event::AIWorkerSlashed {
				worker: worker.clone(),
				inference_id,
				amount: stake,
			});

			Self::deposit_event(Event::AIWorkerBanned {
				worker: worker.clone(),
				inference_id,
			});

			Ok(())
		}

		/// Get inference result for a given inference ID
		pub fn get_inference_result(inference_id: u32) -> Option<InferenceResult<T::AccountId>> {
			InferenceResults::<T>::get(inference_id)
		}

		/// Check if an AIWorker is registered
		pub fn is_ai_worker_registered(account: &T::AccountId) -> bool {
			AIWorkers::<T>::contains_key(account)
		}

		/// Check if an AIValidator is registered
		pub fn is_ai_validator_registered(account: &T::AccountId) -> bool {
			AIValidators::<T>::contains_key(account)
		}

		/// Get allowed model info
		pub fn get_allowed_model(model_id: u32) -> Option<AllowedModel> {
			AllowedModels::<T>::get(model_id)
		}
	}
}
