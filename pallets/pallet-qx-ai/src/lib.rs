//! QX AI pallet - Simplified AI inference system
//!
//! This pallet implements the application layer for QX Chain's civic AI infrastructure.
//!
//! AIWorkers: Civic entities with KILT DIDs that run off-chain AI inference

#![cfg_attr(not(feature = "std"), no_std)]

extern crate alloc;

use frame::prelude::*;
use polkadot_sdk::polkadot_sdk_frame as frame;

use frame::traits::{Currency, ReservableCurrency, Get};

pub use pallet::*;

/// KILT DID identifier type
pub type DidIdentifier = [u8; 32];

/// Allowed model metadata
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
#[codec(mel_bound())]
#[cfg_attr(feature = "std", derive(serde::Serialize, serde::Deserialize))]
pub struct AllowedModel {
	pub model_name: BoundedVec<u8, ConstU32<128>>,  // e.g. "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
	pub model_hash: BoundedVec<u8, ConstU32<64>>,   // Hash of model weights
	pub active: bool,
}

/// Inference status tracking
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub enum InferenceStatus {
	Completed,    // Inference completed successfully
	Failed,       // Inference failed
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
	pub max_tokens: u32,  // Maximum number of tokens to generate
	pub status: RequestStatus,
	pub created_at: u32,
}

/// Inference result data
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct InferenceResult<AccountId> {
	pub request_id: u32,
	pub worker: AccountId,
	pub worker_did: DidIdentifier,
	pub output: BoundedVec<u8, ConstU32<4096>>,
	pub model_id: u32,
	pub status: InferenceStatus,
	pub submitted_at: u32,
}

/// Trait for interacting with KILT permissions pallet
pub trait KiltPermissions<AccountId> {
	fn verify_worker_credential(did: &DidIdentifier) -> Result<bool, DispatchError>;
	fn get_worker_did(account: &AccountId) -> Result<DidIdentifier, DispatchError>;
}

#[frame::pallet]
pub mod pallet {
	use super::*;

	#[pallet::config]
	pub trait Config: polkadot_sdk::frame_system::Config {
		type RuntimeEvent: From<Event<Self>> + IsType<<Self as polkadot_sdk::frame_system::Config>::RuntimeEvent>;

		/// The currency trait for handling token operations (kept for potential future use)
		type Currency: Currency<Self::AccountId> + ReservableCurrency<Self::AccountId>;

		/// KILT permissions pallet interface
		type KiltPermissions: KiltPermissions<Self::AccountId>;

		/// Maximum requests in queue per AIWorker
		#[pallet::constant]
		type MaxQueueSize: Get<u32>;
	}

	#[pallet::pallet]
	pub struct Pallet<T>(_);

	/// Authorized AIWorkers with KILT credentials
	#[pallet::storage]
	pub type AuthorizedWorkers<T: Config> = StorageMap<_, Blake2_128Concat, DidIdentifier, T::AccountId>;

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

	/// Inference results
	#[pallet::storage]
	pub type InferenceResults<T: Config> = StorageMap<_, Blake2_128Concat, u32, InferenceResult<T::AccountId>>;

	/// AIWorker queues - maps AIWorker to list of request IDs
	#[pallet::storage]
	pub type AIWorkerQueues<T: Config> = StorageMap<
		_,
		Blake2_128Concat,
		T::AccountId,
		BoundedVec<u32, T::MaxQueueSize>
	>;

	/// Request to AIWorker mapping
	#[pallet::storage]
	pub type RequestWorkerMap<T: Config> = StorageMap<_, Blake2_128Concat, u32, T::AccountId>;

	/// AIWorker status - true if online/available
	#[pallet::storage]
	pub type AIWorkerStatus<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, bool>;

	/// Events emitted by the pallet
	#[pallet::event]
	#[pallet::generate_deposit(pub(super) fn deposit_event)]
	pub enum Event<T: Config> {
		/// Request submitted to queue
		RequestSubmitted {
			request_id: u32,
			customer: T::AccountId,
			model_id: u32
		},
		/// Request assigned to AIWorker
		RequestAssigned {
			request_id: u32,
			worker: T::AccountId
		},
		/// Inference submitted
		InferenceSubmitted {
			inference_id: u32,
			request_id: u32,
			worker: T::AccountId,
			worker_did: DidIdentifier,
		},
		/// AIWorker status updated
		AIWorkerStatusUpdated {
			worker: T::AccountId,
			online: bool
		},
		/// Request completed
		RequestCompleted {
			request_id: u32,
			inference_id: u32
		},
		/// Model added to allowed registry
		ModelAdded {
			model_id: u32,
			model_name: BoundedVec<u8, ConstU32<128>>
		},
	}

	/// Errors that can be returned by this pallet
	#[pallet::error]
	pub enum Error<T> {
		/// AIWorker not found
		AIWorkerNotFound,
		/// Inference not found
		InferenceNotFound,
		/// Request not found
		RequestNotFound,
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
		/// Worker has no valid credential
		InvalidWorkerCredential,
		/// Worker DID not found
		WorkerDIDNotFound,
	}

	#[pallet::call]
	impl<T: Config> Pallet<T> {
		/// Submit an inference request to a specific AIWorker
		#[pallet::call_index(0)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn submit_request(
			origin: OriginFor<T>,
			target_worker: T::AccountId,
			prompt: BoundedVec<u8, ConstU32<2048>>,
			model_id: u32,
			max_tokens: u32,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			// Check if worker has a DID first before trying to verify credentials
			let worker_did = match T::KiltPermissions::get_worker_did(&target_worker) {
				Ok(did) => did,
				Err(_) => return Err(Error::<T>::WorkerDIDNotFound.into()),
			};

			// Verify worker has valid KILT credential
			let is_valid = match T::KiltPermissions::verify_worker_credential(&worker_did) {
				Ok(valid) => valid,
				Err(_) => false,
			};

			ensure!(is_valid, Error::<T>::InvalidWorkerCredential);

			let model = AllowedModels::<T>::get(model_id).ok_or(Error::<T>::InvalidModel)?;
			ensure!(model.active, Error::<T>::ModelNotActive);

			let request_id = NextRequestId::<T>::get();
			NextRequestId::<T>::put(request_id + 1);

			let current_block = frame_system::Pallet::<T>::block_number();
			let block_number: u32 = current_block.saturated_into();

			let request = InferenceRequest {
				customer: who.clone(),
				target_worker: target_worker.clone(),
				prompt,
				model_id,
				max_tokens,
				status: RequestStatus::Queued,
				created_at: block_number,
			};

			InferenceRequests::<T>::insert(&request_id, &request);
			RequestWorkerMap::<T>::insert(&request_id, &target_worker);

			AIWorkerQueues::<T>::try_mutate(&target_worker, |queue_opt| {
				let queue = queue_opt.get_or_insert_with(|| BoundedVec::new());
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
		#[pallet::call_index(1)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn update_ai_worker_status(
			origin: OriginFor<T>,
			online: bool,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			// Verify worker has valid KILT credential
			let worker_did = T::KiltPermissions::get_worker_did(&who)?;
			ensure!(
				T::KiltPermissions::verify_worker_credential(&worker_did)?,
				Error::<T>::InvalidWorkerCredential
			);

			AIWorkerStatus::<T>::insert(&who, online);

			Self::deposit_event(Event::AIWorkerStatusUpdated {
				worker: who,
				online
			});

			Ok(())
		}

		/// Submit inference result
		#[pallet::call_index(2)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn submit_inference(
			origin: OriginFor<T>,
			request_id: u32,
			output: BoundedVec<u8, ConstU32<4096>>,
			model_id: u32,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			// Verify worker has valid KILT credential
			let worker_did = T::KiltPermissions::get_worker_did(&who)?;
			ensure!(
				T::KiltPermissions::verify_worker_credential(&worker_did)?,
				Error::<T>::InvalidWorkerCredential
			);

			let model = AllowedModels::<T>::get(model_id).ok_or(Error::<T>::InvalidModel)?;
			ensure!(model.active, Error::<T>::ModelNotActive);

			let request = InferenceRequests::<T>::get(&request_id)
				.ok_or(Error::<T>::RequestNotFound)?;

			ensure!(request.target_worker == who, Error::<T>::RequestNotAssigned);
			ensure!(request.status == RequestStatus::Queued, Error::<T>::RequestAlreadyAssigned);
			ensure!(request.model_id == model_id, Error::<T>::InvalidModel);

			let inference_id = NextInferenceId::<T>::get();
			NextInferenceId::<T>::put(inference_id + 1);

			let current_block = frame_system::Pallet::<T>::block_number();
			let block_number: u32 = current_block.saturated_into();

			let result = InferenceResult {
				request_id,
				worker: who.clone(),
				worker_did,
				output,
				model_id,
				status: InferenceStatus::Completed,
				submitted_at: block_number,
			};

			InferenceResults::<T>::insert(&inference_id, &result);

			InferenceRequests::<T>::try_mutate(&request_id, |req_opt| {
				let req = req_opt.as_mut().ok_or(Error::<T>::RequestNotFound)?;
				req.status = RequestStatus::Completed;
				Ok::<(), Error<T>>(())
			})?;

			AIWorkerQueues::<T>::try_mutate(&who, |queue_opt| {
				if let Some(queue) = queue_opt {
					queue.retain(|&id| id != request_id);
				}
				Ok::<(), Error<T>>(())
			})?;

			Self::deposit_event(Event::InferenceSubmitted {
				inference_id,
				request_id,
				worker: who,
				worker_did,
			});

			Self::deposit_event(Event::RequestCompleted {
				request_id,
				inference_id
			});

			Ok(())
		}

		/// Add an allowed model (requires root/sudo)
		#[pallet::call_index(4)]
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
		/// Get inference result for a given inference ID
		pub fn get_inference_result(inference_id: u32) -> Option<InferenceResult<T::AccountId>> {
			InferenceResults::<T>::get(inference_id)
		}

		/// Get allowed model info
		pub fn get_allowed_model(model_id: u32) -> Option<AllowedModel> {
			AllowedModels::<T>::get(model_id)
		}
	}
}