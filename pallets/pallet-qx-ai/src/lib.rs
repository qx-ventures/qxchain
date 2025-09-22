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
	Pending,
	Challenged,
	Validated,
	Slashed,
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
	}

	#[pallet::pallet]
	pub struct Pallet<T>(_);

	/// Workers registered on the network
	#[pallet::storage]
	pub type Workers<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, <T::Currency as Currency<T::AccountId>>::Balance>;

	/// Validators registered on the network
	#[pallet::storage]
	pub type Validators<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, <T::Currency as Currency<T::AccountId>>::Balance>;

	/// Next inference ID
	#[pallet::storage]
	pub type NextInferenceId<T: Config> = StorageValue<_, u32, ValueQuery>;

	/// Events emitted by the pallet
	#[pallet::event]
	#[pallet::generate_deposit(pub(super) fn deposit_event)]
	pub enum Event<T: Config> {
		/// Worker registered
		WorkerRegistered { who: T::AccountId, stake: <T::Currency as Currency<T::AccountId>>::Balance },
		/// Validator registered
		ValidatorRegistered { who: T::AccountId, stake: <T::Currency as Currency<T::AccountId>>::Balance },
		/// Inference submitted
		InferenceSubmitted { inference_id: u32, worker: T::AccountId },
		/// Inference challenged
		InferenceChallenged { inference_id: u32, validator: T::AccountId },
		/// Inference validated
		InferenceValidated { inference_id: u32, validator: T::AccountId },
		/// Worker slashed
		WorkerSlashed { worker: T::AccountId, inference_id: u32, amount: <T::Currency as Currency<T::AccountId>>::Balance },
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

		/// Submit inference result (simplified)
		#[pallet::call_index(2)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn submit_inference(
			origin: OriginFor<T>,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;
			
			ensure!(Workers::<T>::contains_key(&who), Error::<T>::WorkerNotFound);
			
			let inference_id = NextInferenceId::<T>::get();
			NextInferenceId::<T>::put(inference_id + 1);
			
			Self::deposit_event(Event::InferenceSubmitted { inference_id, worker: who });
			Ok(())
		}

		/// Challenge an inference (simplified)
		#[pallet::call_index(3)]
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
		#[pallet::call_index(4)]
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