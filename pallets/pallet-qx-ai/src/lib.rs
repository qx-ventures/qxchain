//! QX AI pallet - Optimistic AI inference verification with challenge-based validation
//!
//! This pallet implements the application layer for QX Chain's civic AI infrastructure.
//! AIWorkers and AIValidators are NOT blockchain consensus nodes - they are application-layer
//! entities that interact with the chain to provide and verify AI services.
//!
//! AIWorkers: Civic entities that run off-chain AI inference and submit cryptographic commitments
//! AIValidators: Independent auditors that challenge incorrect submissions during dispute windows

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
	Pending,      // Submitted, awaiting challenge period
	Challenged,   // Under dispute by validators
	Finalized,    // Challenge period passed, result valid
	Slashed,      // Challenge succeeded, worker slashed
}

/// Request status for tracking
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub enum RequestStatus {
	Queued,
	Assigned,
	Completed,
	Failed,
}

/// Challenge data for tracking validator challenges
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct Challenge<AccountId, Balance> {
	pub validator: AccountId,
	pub expected_output: BoundedVec<u8, ConstU32<4096>>,
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
	pub status: RequestStatus,
	pub created_at: u32,
}

/// Inference result data with cryptographic commitment
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct InferenceResult<AccountId> {
	pub request_id: u32,
	pub worker: AccountId,
	pub output: BoundedVec<u8, ConstU32<4096>>,
	pub model_hash: BoundedVec<u8, ConstU32<64>>, // Cryptographic hash of model used
	pub status: InferenceStatus,
	pub submitted_at: u32,
	pub challenge_deadline: u32, // Block number when challenge period ends
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

		/// Minimum stake required for AIValidators to challenge
		#[pallet::constant]
		type MinChallengeStake: Get<<Self::Currency as Currency<Self::AccountId>>::Balance>;

		/// Challenge period in blocks (7 days in specification)
		#[pallet::constant]
		type ChallengePeriod: Get<BlockNumberFor<Self>>;

		/// Percentage of staked validator weight needed to slash (51% = 51)
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

	/// Next request ID
	#[pallet::storage]
	pub type NextRequestId<T: Config> = StorageValue<_, u32, ValueQuery>;

	/// Next inference ID
	#[pallet::storage]
	pub type NextInferenceId<T: Config> = StorageValue<_, u32, ValueQuery>;

	/// Inference requests in queue
	#[pallet::storage]
	pub type InferenceRequests<T: Config> = StorageMap<_, Blake2_128Concat, u32, InferenceRequest<T::AccountId>>;

	/// Inference results with commitments
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

	/// Challenges for each inference - maps inference_id to list of challenges
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
		/// Inference submitted with cryptographic commitment
		InferenceSubmitted { inference_id: u32, request_id: u32, worker: T::AccountId, challenge_deadline: u32 },
		/// Inference challenged by AIValidator
		InferenceChallenged { inference_id: u32, validator: T::AccountId },
		/// Inference automatically finalized after challenge period
		InferenceFinalized { inference_id: u32, worker: T::AccountId },
		/// AIWorker slashed after successful challenge
		AIWorkerSlashed { worker: T::AccountId, inference_id: u32, amount: <T::Currency as Currency<T::AccountId>>::Balance },
		/// AIWorker banned from network
		AIWorkerBanned { worker: T::AccountId, inference_id: u32 },
		/// Challenge consensus reached (51%+ validators agree)
		ChallengeConsensusReached { inference_id: u32, challenge_stake_weight: u128, total_validator_stake: u128 },
		/// AIWorker status updated
		AIWorkerStatusUpdated { worker: T::AccountId, online: bool },
		/// Request completed
		RequestCompleted { request_id: u32, inference_id: u32 },
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
		/// Already challenged this inference
		AlreadyChallenged,
		/// Cannot challenge own inference
		CannotChallengeSelf,
		/// Inference not in pending status
		InferenceNotPending,
		/// Invalid model parameters
		InvalidModelParameters,
		/// AIWorker queue full
		AIWorkerQueueFull,
		/// No available AIWorkers
		NoAvailableAIWorkers,
		/// Request already assigned
		RequestAlreadyAssigned,
		/// Request not assigned to this AIWorker
		RequestNotAssigned,
		/// Prompt too long
		PromptTooLong,
		/// Output too long
		OutputTooLong,
		/// AIWorker is banned
		AIWorkerBanned,
		/// Challenge output too long
		ChallengeOutputTooLong,
		/// Model hash too long or invalid
		InvalidModelHash,
		/// Challenge period not yet ended
		ChallengePeriodNotEnded,
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

			// Reserve the stake
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

			// Reserve the stake
			T::Currency::reserve(&who, stake)?;

			AIValidators::<T>::insert(&who, stake);

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
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			ensure!(AIWorkers::<T>::contains_key(&target_worker), Error::<T>::AIWorkerNotFound);
			ensure!(!BannedAIWorkers::<T>::contains_key(&target_worker), Error::<T>::AIWorkerBanned);

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

			// Add to AIWorker's queue
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

		/// Submit inference result with cryptographic commitment (immediately returns to citizen)
		#[pallet::call_index(4)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn submit_inference(
			origin: OriginFor<T>,
			request_id: u32,
			output: BoundedVec<u8, ConstU32<4096>>,
			model_hash: BoundedVec<u8, ConstU32<64>>, // Cryptographic commitment to model used
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			ensure!(AIWorkers::<T>::contains_key(&who), Error::<T>::AIWorkerNotFound);
			ensure!(!BannedAIWorkers::<T>::contains_key(&who), Error::<T>::AIWorkerBanned);

			let request = InferenceRequests::<T>::get(&request_id)
				.ok_or(Error::<T>::RequestNotFound)?;

			ensure!(request.target_worker == who, Error::<T>::RequestNotAssigned);
			ensure!(request.status == RequestStatus::Queued, Error::<T>::RequestAlreadyAssigned);

			let bounded_output = output;

			let inference_id = NextInferenceId::<T>::get();
			NextInferenceId::<T>::put(inference_id + 1);

			let current_block = frame_system::Pallet::<T>::block_number();
			let block_number: u32 = current_block.saturated_into();

			// Calculate challenge deadline (7 days per specification)
			let challenge_period: u32 = T::ChallengePeriod::get().saturated_into();
			let challenge_deadline = block_number.saturating_add(challenge_period);

			let result = InferenceResult {
				request_id,
				worker: who.clone(),
				output: bounded_output,
				model_hash,
				status: InferenceStatus::Pending, // Optimistic: assumed valid unless challenged
				submitted_at: block_number,
				challenge_deadline,
			};

			InferenceResults::<T>::insert(&inference_id, &result);

			// Update request status
			InferenceRequests::<T>::try_mutate(&request_id, |req_opt| {
				let req = req_opt.as_mut().ok_or(Error::<T>::RequestNotFound)?;
				req.status = RequestStatus::Completed;
				Ok::<(), Error<T>>(())
			})?;

			// Remove from AIWorker queue
			AIWorkerQueues::<T>::try_mutate(&who, |queue_opt| {
				let queue = queue_opt.as_mut().ok_or(Error::<T>::AIWorkerNotFound)?;
				queue.retain(|&id| id != request_id);
				Ok::<(), Error<T>>(())
			})?;

			Self::deposit_event(Event::InferenceSubmitted {
				inference_id,
				request_id,
				worker: who,
				challenge_deadline,
			});
			Self::deposit_event(Event::RequestCompleted {
				request_id,
				inference_id
			});

			Ok(())
		}

		/// Challenge an inference with expected output (AIValidator disputes AIWorker submission)
		#[pallet::call_index(5)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn challenge_inference(
			origin: OriginFor<T>,
			inference_id: u32,
			expected_output: BoundedVec<u8, ConstU32<4096>>,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			let validator_stake = AIValidators::<T>::get(&who)
				.ok_or(Error::<T>::AIValidatorNotFound)?;

			let inference = InferenceResults::<T>::get(&inference_id)
				.ok_or(Error::<T>::InferenceNotFound)?;

			ensure!(inference.status == InferenceStatus::Pending, Error::<T>::InferenceNotPending);
			ensure!(inference.worker != who, Error::<T>::CannotChallengeSelf);

			let current_block = frame_system::Pallet::<T>::block_number();
			let block_number: u32 = current_block.saturated_into();

			// Ensure within 7-day challenge period
			ensure!(block_number <= inference.challenge_deadline, Error::<T>::ChallengePeriodExpired);

			let challenge = Challenge {
				validator: who.clone(),
				expected_output: expected_output.clone(),
				submitted_at: block_number,
				stake: validator_stake, // Include stake for weighted consensus
			};

			// Check if AIValidator already challenged this inference
			if let Some(existing_challenges) = InferenceChallenges::<T>::get(&inference_id) {
				ensure!(!existing_challenges.iter().any(|c| c.validator == who), Error::<T>::AlreadyChallenged);
			}

			// Add challenge to storage
			InferenceChallenges::<T>::try_mutate(&inference_id, |challenges_opt| {
				let challenges = challenges_opt.get_or_insert_with(|| BoundedVec::new());
				challenges.try_push(challenge).map_err(|_| Error::<T>::AIWorkerQueueFull)?;
				Ok::<(), Error<T>>(())
			})?;

			// Update inference status to challenged
			InferenceResults::<T>::try_mutate(&inference_id, |result_opt| {
				let result = result_opt.as_mut().ok_or(Error::<T>::InferenceNotFound)?;
				result.status = InferenceStatus::Challenged;
				Ok::<(), Error<T>>(())
			})?;

			// Check for 51% consensus after adding challenge
			Self::check_challenge_consensus(inference_id, expected_output)?;

			Self::deposit_event(Event::InferenceChallenged { inference_id, validator: who });
			Ok(())
		}

		/// Finalize inference after challenge period ends (anyone can call to trigger finalization)
		#[pallet::call_index(6)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn finalize_inference(
			origin: OriginFor<T>,
			inference_id: u32,
		) -> DispatchResult {
			let _who = ensure_signed(origin)?;

			let inference = InferenceResults::<T>::get(&inference_id)
				.ok_or(Error::<T>::InferenceNotFound)?;

			let current_block = frame_system::Pallet::<T>::block_number();
			let block_number: u32 = current_block.saturated_into();

			// Ensure challenge period has ended
			ensure!(block_number > inference.challenge_deadline, Error::<T>::ChallengePeriodNotEnded);

			// Only finalize if still pending (not already slashed or finalized)
			ensure!(inference.status == InferenceStatus::Pending, Error::<T>::InferenceNotPending);

			// Update status to finalized
			InferenceResults::<T>::try_mutate(&inference_id, |result_opt| {
				let result = result_opt.as_mut().ok_or(Error::<T>::InferenceNotFound)?;
				result.status = InferenceStatus::Finalized;
				Ok::<(), Error<T>>(())
			})?;

			Self::deposit_event(Event::InferenceFinalized {
				inference_id,
				worker: inference.worker.clone()
			});

			Ok(())
		}
	}

	impl<T: Config> Pallet<T> {
		/// Check if challenge consensus is reached (51%+ of staked validator weight agrees)
		fn check_challenge_consensus(
			inference_id: u32,
			expected_output: BoundedVec<u8, ConstU32<4096>>,
		) -> DispatchResult {
			let challenges = InferenceChallenges::<T>::get(&inference_id)
				.unwrap_or_default();

			// Calculate total stake weight of validators challenging with matching expected output
			let challenging_stake_weight: u128 = challenges.iter()
				.filter(|c| c.expected_output == expected_output)
				.map(|c| {
					let balance: u128 = c.stake.saturated_into();
					balance
				})
				.sum();

			// Get total stake of all registered AIValidators
			let total_validator_stake: u128 = AIValidators::<T>::iter()
				.map(|(_, stake)| {
					let balance: u128 = stake.saturated_into();
					balance
				})
				.sum();

			// Check if we have 51%+ consensus (using threshold from config)
			let threshold_percent = T::SlashThreshold::get() as u128;
			let required_stake = (total_validator_stake * threshold_percent) / 100;

			if challenging_stake_weight >= required_stake && total_validator_stake > 0 {
				Self::deposit_event(Event::ChallengeConsensusReached {
					inference_id,
					challenge_stake_weight: challenging_stake_weight,
					total_validator_stake,
				});

				// Execute slashing and banning
				Self::slash_and_ban_ai_worker(inference_id)?;
			}

			Ok(())
		}

		/// Slash AIWorker stake and ban them from the network after successful challenge
		fn slash_and_ban_ai_worker(inference_id: u32) -> DispatchResult {
			let inference = InferenceResults::<T>::get(&inference_id)
				.ok_or(Error::<T>::InferenceNotFound)?;

			let worker = &inference.worker;

			// Get AIWorker's stake
			let stake = AIWorkers::<T>::get(worker)
				.ok_or(Error::<T>::AIWorkerNotFound)?;

			// Slash the AIWorker's stake (confiscate it)
			let _ = T::Currency::slash_reserved(worker, stake);

			// Ban the AIWorker
			BannedAIWorkers::<T>::insert(worker, true);

			// Remove AIWorker from active workers
			AIWorkers::<T>::remove(worker);
			AIWorkerQueues::<T>::remove(worker);
			AIWorkerStatus::<T>::remove(worker);

			// Update inference status to slashed
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
	}
}
