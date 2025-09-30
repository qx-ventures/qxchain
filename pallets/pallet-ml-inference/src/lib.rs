//! ML Inference Pallet - Decentralized machine learning inference validation
//!
//! This pallet manages ML inference requests, worker/validator coordination, and consensus-based validation.

#![cfg_attr(not(feature = "std"), no_std)]

use frame::prelude::*;
use polkadot_sdk::polkadot_sdk_frame as frame;

// Import necessary traits and types
use frame::traits::Get;

pub mod types;
pub use types::*;

// Re-export all pallet parts, this is needed to properly import the pallet into the runtime.
pub use pallet::*;

// Types are now imported from the types module

#[frame::pallet]
pub mod pallet {
	use super::*;

	#[pallet::config]
	pub trait Config: polkadot_sdk::frame_system::Config {
		type RuntimeEvent: From<Event<Self>> + IsType<<Self as polkadot_sdk::frame_system::Config>::RuntimeEvent>;

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
	pub type Workers<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, bool>;

	/// Validators registered on the network
	#[pallet::storage]
	pub type Validators<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, bool>;

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

	/// Events emitted by the pallet
	#[pallet::event]
	#[pallet::generate_deposit(pub(super) fn deposit_event)]
	pub enum Event<T: Config> {
		/// Worker registered
		WorkerRegistered { who: T::AccountId },
		/// Validator registered
		ValidatorRegistered { who: T::AccountId },
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
		/// Worker banned from network
		WorkerBanned { worker: T::AccountId, inference_id: u32 },
		/// Challenge consensus reached
		ChallengeConsensusReached { inference_id: u32, challenge_count: u32, total_validators: u32 },
		/// Worker status updated
		WorkerStatusUpdated { worker: T::AccountId, online: bool },
		/// Request completed
		RequestCompleted { request_id: u32, inference_id: u32 },
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
	}

	#[pallet::call]
	impl<T: Config> Pallet<T> {
		/// Register as a worker
		#[pallet::call_index(0)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn register_worker(
			origin: OriginFor<T>,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			ensure!(!Workers::<T>::contains_key(&who), Error::<T>::WorkerAlreadyRegistered);
			ensure!(!BannedWorkers::<T>::contains_key(&who), Error::<T>::WorkerBanned);

			Workers::<T>::insert(&who, true);
			WorkerQueues::<T>::insert(&who, BoundedVec::new());
			WorkerStatus::<T>::insert(&who, false);

			Self::deposit_event(Event::WorkerRegistered { who });
			Ok(())
		}

		/// Register as a validator
		#[pallet::call_index(1)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn register_validator(
			origin: OriginFor<T>,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			ensure!(!Validators::<T>::contains_key(&who), Error::<T>::ValidatorAlreadyRegistered);

			Validators::<T>::insert(&who, true);

			Self::deposit_event(Event::ValidatorRegistered { who });
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
		
		/// Ban worker from the network
		fn slash_and_ban_worker(inference_id: u32) -> DispatchResult {
			let inference = InferenceResults::<T>::get(&inference_id)
				.ok_or(Error::<T>::InferenceNotFound)?;

			let worker = &inference.worker;

			// Ban the worker
			BannedWorkers::<T>::insert(worker, true);

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

			Self::deposit_event(Event::WorkerBanned {
				worker: worker.clone(),
				inference_id,
			});
			Ok(())
		}
	}
}