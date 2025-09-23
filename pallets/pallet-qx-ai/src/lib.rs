//! QX opML pallet - Decentralized AI inference validation with staking and slashing

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

		/// Challenge an inference (simplified)
		#[pallet::call_index(5)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn challenge_inference(
			origin: OriginFor<T>,
			inference_id: u32,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;
			
			ensure!(Validators::<T>::contains_key(&who), Error::<T>::ValidatorNotFound);
			
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
}