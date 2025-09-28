//! ML Inference Pallet - Decentralized machine learning inference validation with staking and slashing
//!
//! This pallet manages ML inference requests, worker/validator coordination, and consensus-based validation.

#![cfg_attr(not(feature = "std"), no_std)]

use frame::prelude::*;
use polkadot_sdk::polkadot_sdk_frame as frame;

// Import necessary traits and types
use frame::traits::{Currency, ReservableCurrency, Get};

// Re-export all pallet parts, this is needed to properly import the pallet into the runtime.
pub use pallet::*;

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

/// Node identity information for linking workers/validators to blockchain nodes
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct NodeIdentity {
	pub peer_id: BoundedVec<u8, ConstU32<64>>,
	pub endpoint: BoundedVec<u8, ConstU32<256>>,
	pub node_type: NodeType,
}

/// Node type classification
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub enum NodeType {
	Worker,
	Validator,
	WorkerValidator, // Node that can be both
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

/// Request status for tracking
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub enum RequestStatus {
	Queued,
	Assigned,
	Completed,
	Failed,
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

#[frame::pallet]
pub mod pallet {
	use super::*;

	#[pallet::config]
	pub trait Config: polkadot_sdk::frame_system::Config {
		type RuntimeEvent: From<Event<Self>> + IsType<<Self as polkadot_sdk::frame_system::Config>::RuntimeEvent>;
		
		/// The currency trait for handling token operations
		type Currency: Currency<Self::AccountId> + ReservableCurrency<Self::AccountId>;
		
		/// Minimum stake required for workers
		#[pallet::constant]
		type MinWorkerStake: Get<<Self::Currency as Currency<Self::AccountId>>::Balance>;
		
		/// Minimum stake required for validators to challenge
		#[pallet::constant]
		type MinChallengeStake: Get<<Self::Currency as Currency<Self::AccountId>>::Balance>;
		
		/// Challenge period in blocks
		#[pallet::constant]
		type ChallengePeriod: Get<BlockNumberFor<Self>>;
		
		/// Percentage of validators needed to slash (e.g., 51 = 51%)
		#[pallet::constant]
		type SlashThreshold: Get<u32>;
		
		/// Maximum requests in queue per worker
		#[pallet::constant]
		type MaxQueueSize: Get<u32>;
	}

	#[pallet::pallet]
	pub struct Pallet<T>(_);

	/// Workers registered on the network
	#[pallet::storage]
	pub type Workers<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, <T::Currency as Currency<T::AccountId>>::Balance>;

	/// Validators registered on the network
	#[pallet::storage]
	pub type Validators<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, <T::Currency as Currency<T::AccountId>>::Balance>;

	/// Next request ID
	#[pallet::storage]
	pub type NextRequestId<T: Config> = StorageValue<_, u32, ValueQuery>;

	/// Next inference ID
	#[pallet::storage]
	pub type NextInferenceId<T: Config> = StorageValue<_, u32, ValueQuery>;

	/// Inference requests in queue
	#[pallet::storage]
	pub type InferenceRequests<T: Config> = StorageMap<_, Blake2_128Concat, u32, InferenceRequest<T::AccountId>>;

	/// Inference results
	#[pallet::storage]
	pub type InferenceResults<T: Config> = StorageMap<_, Blake2_128Concat, u32, InferenceResult<T::AccountId>>;

	/// Worker queues - maps worker to list of request IDs
	#[pallet::storage]
	pub type WorkerQueues<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, BoundedVec<u32, T::MaxQueueSize>>;

	/// Request to worker mapping
	#[pallet::storage]
	pub type RequestWorkerMap<T: Config> = StorageMap<_, Blake2_128Concat, u32, T::AccountId>;

	/// Worker status - true if online/available
	#[pallet::storage]
	pub type WorkerStatus<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, bool>;

	/// Challenges for each inference - maps inference_id to list of challenges
	#[pallet::storage]
	pub type InferenceChallenges<T: Config> = StorageMap<_, Blake2_128Concat, u32, BoundedVec<Challenge<T::AccountId>, ConstU32<100>>>;

	/// Banned workers - workers that have been slashed and removed from network
	#[pallet::storage]
	pub type BannedWorkers<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, bool>;

	/// Node identities - maps account to node identity information
	#[pallet::storage]
	pub type NodeIdentities<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, NodeIdentity>;

	/// Node to account mapping - maps peer_id to account
	#[pallet::storage]
	pub type NodeToAccount<T: Config> = StorageMap<_, Blake2_128Concat, BoundedVec<u8, ConstU32<64>>, T::AccountId>;

	/// Slashed nodes - nodes that have been slashed and should be disconnected
	#[pallet::storage]
	pub type SlashedNodes<T: Config> = StorageMap<_, Blake2_128Concat, BoundedVec<u8, ConstU32<64>>, bool>;

	/// Events emitted by the pallet
	#[pallet::event]
	#[pallet::generate_deposit(pub(super) fn deposit_event)]
	pub enum Event<T: Config> {
		/// Worker registered
		WorkerRegistered { who: T::AccountId, stake: <T::Currency as Currency<T::AccountId>>::Balance },
		/// Validator registered
		ValidatorRegistered { who: T::AccountId, stake: <T::Currency as Currency<T::AccountId>>::Balance },
		/// Request submitted to queue
		RequestSubmitted { request_id: u32, customer: T::AccountId, model_id: u32 },
		/// Request assigned to worker
		RequestAssigned { request_id: u32, worker: T::AccountId },
		/// Inference submitted
		InferenceSubmitted { inference_id: u32, request_id: u32, worker: T::AccountId },
		/// Inference challenged
		InferenceChallenged { inference_id: u32, validator: T::AccountId },
		/// Inference validated
		InferenceValidated { inference_id: u32, validator: T::AccountId },
		/// Worker slashed
		WorkerSlashed { worker: T::AccountId, inference_id: u32, amount: <T::Currency as Currency<T::AccountId>>::Balance },
		/// Worker banned from network
		WorkerBanned { worker: T::AccountId, inference_id: u32 },
		/// Challenge consensus reached
		ChallengeConsensusReached { inference_id: u32, challenge_count: u32, total_validators: u32 },
		/// Worker status updated
		WorkerStatusUpdated { worker: T::AccountId, online: bool },
		/// Request completed
		RequestCompleted { request_id: u32, inference_id: u32 },
		/// Node identity registered
		NodeIdentityRegistered { account: T::AccountId, peer_id: BoundedVec<u8, ConstU32<64>>, node_type: u8 },
		/// Node slashed due to worker/validator slashing
		NodeSlashed { account: T::AccountId, peer_id: BoundedVec<u8, ConstU32<64>>, reason: u8 },
	}

	/// Errors that can be returned by this pallet
	#[pallet::error]
	pub enum Error<T> {
		/// Worker already registered
		WorkerAlreadyRegistered,
		/// Validator already registered
		ValidatorAlreadyRegistered,
		/// Worker not found
		WorkerNotFound,
		/// Validator not found
		ValidatorNotFound,
		/// Inference not found
		InferenceNotFound,
		/// Request not found
		RequestNotFound,
		/// Insufficient stake
		InsufficientStake,
		/// Challenge period expired
		ChallengePeriodExpired,
		/// Already challenged this inference
		AlreadyChallenged,
		/// Cannot challenge own inference
		CannotChallengeSelf,
		/// Inference not in pending status
		InferenceNotPending,
		/// Invalid model parameters
		InvalidModelParameters,
		/// Worker queue full
		WorkerQueueFull,
		/// No available workers
		NoAvailableWorkers,
		/// Request already assigned
		RequestAlreadyAssigned,
		/// Request not assigned to this worker
		RequestNotAssigned,
		/// Prompt too long
		PromptTooLong,
		/// Output too long
		OutputTooLong,
		/// Worker is banned
		WorkerBanned,
		/// Challenge output too long
		ChallengeOutputTooLong,
		/// Node identity already registered
		NodeIdentityAlreadyRegistered,
		/// Invalid node identity format
		InvalidNodeIdentity,
		/// Node identity not found
		NodeIdentityNotFound,
		/// Invalid peer ID format
		InvalidPeerId,
		/// Node already slashed
		NodeAlreadySlashed,
	}

	#[pallet::call]
	impl<T: Config> Pallet<T> {
		/// Register as a worker with stake
		#[pallet::call_index(0)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn register_worker(
			origin: OriginFor<T>,
			stake: <T::Currency as Currency<T::AccountId>>::Balance,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;
			
			ensure!(!Workers::<T>::contains_key(&who), Error::<T>::WorkerAlreadyRegistered);
			ensure!(!BannedWorkers::<T>::contains_key(&who), Error::<T>::WorkerBanned);
			ensure!(stake >= T::MinWorkerStake::get(), Error::<T>::InsufficientStake);
			
			// Reserve the stake
			T::Currency::reserve(&who, stake)?;
			
			Workers::<T>::insert(&who, stake);
			WorkerQueues::<T>::insert(&who, BoundedVec::new());
			WorkerStatus::<T>::insert(&who, false);
			
			Self::deposit_event(Event::WorkerRegistered { who, stake });
			Ok(())
		}

		/// Register as a validator with stake
		#[pallet::call_index(1)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn register_validator(
			origin: OriginFor<T>,
			stake: <T::Currency as Currency<T::AccountId>>::Balance,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;
			
			ensure!(!Validators::<T>::contains_key(&who), Error::<T>::ValidatorAlreadyRegistered);
			ensure!(stake >= T::MinChallengeStake::get(), Error::<T>::InsufficientStake);
			
			// Reserve the stake
			T::Currency::reserve(&who, stake)?;
			
			Validators::<T>::insert(&who, stake);
			
			Self::deposit_event(Event::ValidatorRegistered { who, stake });
			Ok(())
		}

		/// Submit an inference request to a specific worker
		#[pallet::call_index(2)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn submit_request(
			origin: OriginFor<T>,
			target_worker: T::AccountId,
			prompt: BoundedVec<u8, ConstU32<2048>>,
			model_id: u32,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;
			
			ensure!(Workers::<T>::contains_key(&target_worker), Error::<T>::WorkerNotFound);
			ensure!(!BannedWorkers::<T>::contains_key(&target_worker), Error::<T>::WorkerBanned);
			
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
				status: RequestStatus::Queued,
				created_at: block_number,
			};
			
			InferenceRequests::<T>::insert(&request_id, &request);
			RequestWorkerMap::<T>::insert(&request_id, &target_worker);
			
			// Add to worker's queue
			WorkerQueues::<T>::try_mutate(&target_worker, |queue_opt| {
				let queue = queue_opt.as_mut().ok_or(Error::<T>::WorkerNotFound)?;
				queue.try_push(request_id).map_err(|_| Error::<T>::WorkerQueueFull)?;
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

		/// Update worker online status
		#[pallet::call_index(3)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn update_worker_status(
			origin: OriginFor<T>,
			online: bool,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;
			
			ensure!(Workers::<T>::contains_key(&who), Error::<T>::WorkerNotFound);
			
			WorkerStatus::<T>::insert(&who, online);
			
			Self::deposit_event(Event::WorkerStatusUpdated { 
				worker: who, 
				online 
			});
			
			Ok(())
		}

		/// Submit inference result for a request
		#[pallet::call_index(4)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn submit_inference(
			origin: OriginFor<T>,
			request_id: u32,
			output: BoundedVec<u8, ConstU32<4096>>,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;
			
			ensure!(Workers::<T>::contains_key(&who), Error::<T>::WorkerNotFound);
			ensure!(!BannedWorkers::<T>::contains_key(&who), Error::<T>::WorkerBanned);
			
			let request = InferenceRequests::<T>::get(&request_id)
				.ok_or(Error::<T>::RequestNotFound)?;
			
			ensure!(request.target_worker == who, Error::<T>::RequestNotAssigned);
			ensure!(request.status == RequestStatus::Queued, Error::<T>::RequestAlreadyAssigned);
			
			let bounded_output = output;
			
			let inference_id = NextInferenceId::<T>::get();
			NextInferenceId::<T>::put(inference_id + 1);
			
			let current_block = frame_system::Pallet::<T>::block_number();
			let block_number: u32 = current_block.saturated_into();
			
			let result = InferenceResult {
				request_id,
				worker: who.clone(),
				output: bounded_output,
				status: InferenceStatus::Pending,
				submitted_at: block_number,
			};
			
			InferenceResults::<T>::insert(&inference_id, &result);
			
			// Update request status
			InferenceRequests::<T>::try_mutate(&request_id, |req_opt| {
				let req = req_opt.as_mut().ok_or(Error::<T>::RequestNotFound)?;
				req.status = RequestStatus::Completed;
				Ok::<(), Error<T>>(())
			})?;
			
			// Remove from worker queue
			WorkerQueues::<T>::try_mutate(&who, |queue_opt| {
				let queue = queue_opt.as_mut().ok_or(Error::<T>::WorkerNotFound)?;
				queue.retain(|&id| id != request_id);
				Ok::<(), Error<T>>(())
			})?;
			
			Self::deposit_event(Event::InferenceSubmitted { 
				inference_id, 
				request_id,
				worker: who 
			});
			Self::deposit_event(Event::RequestCompleted { 
				request_id, 
				inference_id 
			});
			
			Ok(())
		}

		/// Challenge an inference with expected output
		#[pallet::call_index(5)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn challenge_inference(
			origin: OriginFor<T>,
			inference_id: u32,
			expected_output: BoundedVec<u8, ConstU32<4096>>,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;
			
			ensure!(Validators::<T>::contains_key(&who), Error::<T>::ValidatorNotFound);
			
			let inference = InferenceResults::<T>::get(&inference_id)
				.ok_or(Error::<T>::InferenceNotFound)?;
			
			ensure!(inference.status == InferenceStatus::Pending, Error::<T>::InferenceNotPending);
			ensure!(inference.worker != who, Error::<T>::CannotChallengeSelf);
			
			let current_block = frame_system::Pallet::<T>::block_number();
			let block_number: u32 = current_block.saturated_into();
			
			let challenge = Challenge {
				validator: who.clone(),
				expected_output: expected_output.clone(),
				submitted_at: block_number,
			};
			
			// Check if validator already challenged this inference
			if let Some(existing_challenges) = InferenceChallenges::<T>::get(&inference_id) {
				ensure!(!existing_challenges.iter().any(|c| c.validator == who), Error::<T>::AlreadyChallenged);
			}
			
			// Add challenge to storage
			InferenceChallenges::<T>::try_mutate(&inference_id, |challenges_opt| {
				let challenges = challenges_opt.get_or_insert_with(|| BoundedVec::new());
				challenges.try_push(challenge).map_err(|_| Error::<T>::WorkerQueueFull)?;
				Ok::<(), Error<T>>(())
			})?;
			
			// Update inference status to challenged
			InferenceResults::<T>::try_mutate(&inference_id, |result_opt| {
				let result = result_opt.as_mut().ok_or(Error::<T>::InferenceNotFound)?;
				result.status = InferenceStatus::Challenged;
				Ok::<(), Error<T>>(())
			})?;
			
			// Check for consensus after adding challenge
			Self::check_challenge_consensus(inference_id, expected_output)?;
			
			Self::deposit_event(Event::InferenceChallenged { inference_id, validator: who });
			Ok(())
		}

		/// Validate an inference as correct
		#[pallet::call_index(6)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn validate_inference(
			origin: OriginFor<T>,
			inference_id: u32,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;
			
			ensure!(Validators::<T>::contains_key(&who), Error::<T>::ValidatorNotFound);
			
			Self::deposit_event(Event::InferenceValidated { inference_id, validator: who });
			Ok(())
		}

		/// Register or update node identity for an existing worker/validator
		#[pallet::call_index(7)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn register_node_identity(
			origin: OriginFor<T>,
			peer_id: BoundedVec<u8, ConstU32<64>>,
			endpoint: BoundedVec<u8, ConstU32<256>>,
			node_type: u8, // 0=Worker, 1=Validator, 2=WorkerValidator
		) -> DispatchResult {
			let who = ensure_signed(origin)?;
			
			// Ensure the account is either a worker or validator
			ensure!(
				Workers::<T>::contains_key(&who) || Validators::<T>::contains_key(&who),
				Error::<T>::WorkerNotFound
			);
			
			// Convert node_type u8 to enum
			let node_type_enum = match node_type {
				0 => NodeType::Worker,
				1 => NodeType::Validator,
				2 => NodeType::WorkerValidator,
				_ => return Err(Error::<T>::InvalidNodeIdentity.into()),
			};
			
			// Check if peer_id is already registered to another account
			if let Some(existing_account) = NodeToAccount::<T>::get(&peer_id) {
				ensure!(existing_account == who, Error::<T>::NodeIdentityAlreadyRegistered);
			}
			
			// Remove old mapping if exists
			if let Some(old_identity) = NodeIdentities::<T>::get(&who) {
				NodeToAccount::<T>::remove(&old_identity.peer_id);
			}
			
			let node_identity = NodeIdentity {
				peer_id: peer_id.clone(),
				endpoint,
				node_type: node_type_enum.clone(),
			};
			
			NodeIdentities::<T>::insert(&who, &node_identity);
			NodeToAccount::<T>::insert(&peer_id, &who);
			
			Self::deposit_event(Event::NodeIdentityRegistered { 
				account: who, 
				peer_id, 
				node_type 
			});
			
			Ok(())
		}
	}

	impl<T: Config> Pallet<T> {
		/// Check if challenge consensus is reached (2/3+ validators agree)
		fn check_challenge_consensus(
			inference_id: u32,
			expected_output: BoundedVec<u8, ConstU32<4096>>,
		) -> DispatchResult {
			let challenges = InferenceChallenges::<T>::get(&inference_id)
				.unwrap_or_default();
			
			// Count validators with matching expected output
			let matching_challenges = challenges.iter()
				.filter(|c| c.expected_output == expected_output)
				.count() as u32;
			
			// Get total number of registered validators
			let total_validators = Validators::<T>::iter().count() as u32;
			
			// Check if we have 2/3+ consensus (using ceiling division)
			let required_consensus = (total_validators * 2 + 2) / 3; // Ceiling of 2/3
			
			if matching_challenges >= required_consensus && total_validators > 0 {
				Self::deposit_event(Event::ChallengeConsensusReached {
					inference_id,
					challenge_count: matching_challenges,
					total_validators,
				});
				
				// Execute slashing and banning
				Self::slash_and_ban_worker(inference_id)?;
			}
			
			Ok(())
		}
		
		/// Slash worker stake and ban them from the network, including node-level slashing
		fn slash_and_ban_worker(inference_id: u32) -> DispatchResult {
			let inference = InferenceResults::<T>::get(&inference_id)
				.ok_or(Error::<T>::InferenceNotFound)?;
			
			let worker = &inference.worker;
			
			// Get worker's stake
			let stake = Workers::<T>::get(worker)
				.ok_or(Error::<T>::WorkerNotFound)?;
			
			// Slash the worker's stake (confiscate it)
			let _ = T::Currency::slash_reserved(worker, stake);
			
			// Ban the worker
			BannedWorkers::<T>::insert(worker, true);
			
			// Slash the associated node if it exists
			if let Some(node_identity) = NodeIdentities::<T>::get(worker) {
				SlashedNodes::<T>::insert(&node_identity.peer_id, true);
				
				Self::deposit_event(Event::NodeSlashed {
					account: worker.clone(),
					peer_id: node_identity.peer_id,
					reason: 0, // WorkerSlashed
				});
			}
			
			// Remove worker from active workers
			Workers::<T>::remove(worker);
			WorkerQueues::<T>::remove(worker);
			WorkerStatus::<T>::remove(worker);
			
			// Update inference status to slashed
			InferenceResults::<T>::try_mutate(&inference_id, |result_opt| {
				let result = result_opt.as_mut().ok_or(Error::<T>::InferenceNotFound)?;
				result.status = InferenceStatus::Slashed;
				Ok::<(), Error<T>>(())
			})?;
			
			Self::deposit_event(Event::WorkerSlashed {
				worker: worker.clone(),
				inference_id,
				amount: stake,
			});
			
			Self::deposit_event(Event::WorkerBanned {
				worker: worker.clone(),
				inference_id,
			});
			
			Ok(())
		}
		
		/// Check if a node is slashed
		pub fn is_node_slashed(peer_id: &BoundedVec<u8, ConstU32<64>>) -> bool {
			SlashedNodes::<T>::get(peer_id).unwrap_or(false)
		}
		
		/// Get node identity for account
		pub fn get_node_identity(account: &T::AccountId) -> Option<NodeIdentity> {
			NodeIdentities::<T>::get(account)
		}
		
		/// Get account for node peer_id
		pub fn get_account_for_node(peer_id: &BoundedVec<u8, ConstU32<64>>) -> Option<T::AccountId> {
			NodeToAccount::<T>::get(peer_id)
		}
		
	}
}