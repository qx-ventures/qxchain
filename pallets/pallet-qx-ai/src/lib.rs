//! QX opML pallet - simple version following minimal template pattern

#![cfg_attr(not(feature = "std"), no_std)]

use frame::prelude::*;
use polkadot_sdk::polkadot_sdk_frame as frame;

// Re-export all pallet parts, this is needed to properly import the pallet into the runtime.
pub use pallet::*;

#[frame::pallet]
pub mod pallet {
	use super::*;

	#[pallet::config]
	pub trait Config: polkadot_sdk::frame_system::Config {}

	#[pallet::pallet]
	pub struct Pallet<T>(_);

	/// Simple storage for worker count
	#[pallet::storage]
	pub type WorkerCount<T> = StorageValue<Value = u32>;

	/// Simple storage for inference count
	#[pallet::storage]
	pub type InferenceCount<T> = StorageValue<Value = u32>;

	#[pallet::call]
	impl<T: Config> Pallet<T> {
		/// Register as a worker
		#[pallet::call_index(0)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn register_worker(origin: OriginFor<T>) -> DispatchResult {
			let _who = ensure_signed(origin)?;
			
			let current = WorkerCount::<T>::get().unwrap_or(0);
			WorkerCount::<T>::put(current + 1);
			
			Ok(())
		}

		/// Request inference
		#[pallet::call_index(1)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn request_inference(origin: OriginFor<T>) -> DispatchResult {
			let _who = ensure_signed(origin)?;
			
			let current = InferenceCount::<T>::get().unwrap_or(0);
			InferenceCount::<T>::put(current + 1);
			
			Ok(())
		}
	}
}