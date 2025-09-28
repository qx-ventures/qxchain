//! ML Models Pallet - Model registry and management for decentralized ML inference
//!
//! This pallet manages AI/ML model registration, versioning, and provider configuration.

#![cfg_attr(not(feature = "std"), no_std)]

use frame::prelude::*;
use polkadot_sdk::polkadot_sdk_frame as frame;

// Import necessary traits
use frame::traits::Get;

// Re-export pallet parts
pub use pallet::*;

/// Model configuration
#[derive(Encode, Decode, Clone, PartialEq, Eq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct ModelConfig<AccountId> {
	pub owner: AccountId,
	pub name: BoundedVec<u8, ConstU32<64>>,
	pub provider_type: u8, // 0=OpenAI, 1=Ollama, 2=LMStudio, 3=Custom
	pub endpoint: BoundedVec<u8, ConstU32<256>>,
	pub model_identifier: BoundedVec<u8, ConstU32<128>>,
	pub requires_api_key: bool,
	pub default_temperature: u16,
	pub default_max_tokens: u32,
	pub default_seed: u32,
	pub is_active: bool,
	pub created_at: u32,
	pub updated_at: u32,
}

#[frame::pallet]
pub mod pallet {
	use super::*;

	#[pallet::config]
	pub trait Config: polkadot_sdk::frame_system::Config {
		type RuntimeEvent: From<Event<Self>> + IsType<<Self as polkadot_sdk::frame_system::Config>::RuntimeEvent>;

		/// Maximum number of models per owner
		#[pallet::constant]
		type MaxModelsPerOwner: Get<u32>;

		/// Maximum number of total models in the system
		#[pallet::constant]
		type MaxTotalModels: Get<u32>;
	}

	#[pallet::pallet]
	pub struct Pallet<T>(_);

	/// Next model ID
	#[pallet::storage]
	pub type NextModelId<T: Config> = StorageValue<_, u32, ValueQuery>;

	/// Model configurations
	#[pallet::storage]
	pub type Models<T: Config> = StorageMap<_, Blake2_128Concat, u32, ModelConfig<T::AccountId>>;

	/// Owner to model IDs mapping
	#[pallet::storage]
	pub type OwnerModels<T: Config> = StorageMap<
		_,
		Blake2_128Concat,
		T::AccountId,
		BoundedVec<u32, T::MaxModelsPerOwner>,
		ValueQuery
	>;

	/// Events emitted by the pallet
	#[pallet::event]
	#[pallet::generate_deposit(pub(super) fn deposit_event)]
	pub enum Event<T: Config> {
		/// Model registered
		ModelRegistered {
			model_id: u32,
			owner: T::AccountId,
		},

		/// Model updated
		ModelUpdated {
			model_id: u32,
			owner: T::AccountId,
		},

		/// Model status changed
		ModelStatusChanged {
			model_id: u32,
			is_active: bool,
		},
	}

	/// Errors that can be returned by this pallet
	#[pallet::error]
	pub enum Error<T> {
		/// Model not found
		ModelNotFound,
		/// Not the model owner
		NotModelOwner,
		/// Maximum models per owner exceeded
		MaxModelsPerOwnerExceeded,
		/// Invalid temperature value
		InvalidTemperature,
		/// Model is disabled
		ModelDisabled,
		/// API key required but not provided
		ApiKeyRequired,
	}

	#[pallet::call]
	impl<T: Config> Pallet<T> {
		/// Register a new AI model
		#[pallet::call_index(0)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn register_model(
			origin: OriginFor<T>,
			name: BoundedVec<u8, ConstU32<64>>,
			provider_type: u8,
			endpoint: BoundedVec<u8, ConstU32<256>>,
			model_identifier: BoundedVec<u8, ConstU32<128>>,
			temperature: u16,
			max_tokens: u32,
			seed: u32,
		) -> DispatchResult {
			let owner = ensure_signed(origin)?;

			// Validate temperature (0-2000, representing 0.0-2.0)
			ensure!(temperature <= 2000, Error::<T>::InvalidTemperature);

			// Check owner's model limit
			let mut owner_models = OwnerModels::<T>::get(&owner);
			ensure!(
				owner_models.len() < T::MaxModelsPerOwner::get() as usize,
				Error::<T>::MaxModelsPerOwnerExceeded
			);

			// Get next model ID
			let model_id = NextModelId::<T>::get();
			NextModelId::<T>::put(model_id + 1);

			// Get current block number for timestamps
			let current_block = <polkadot_sdk::frame_system::Pallet<T>>::block_number();
			let block_u32 = TryInto::<u32>::try_into(current_block).unwrap_or(0);

			// Create model configuration
			let model_config = ModelConfig {
				owner: owner.clone(),
				name: name.clone(),
				provider_type,
				endpoint,
				model_identifier,
				requires_api_key: provider_type == 0, // OpenAI requires API key
				default_temperature: temperature,
				default_max_tokens: max_tokens,
				default_seed: seed,
				is_active: true,
				created_at: block_u32,
				updated_at: block_u32,
			};

			// Store model
			Models::<T>::insert(model_id, &model_config);

			// Update owner's model list
			owner_models.try_push(model_id).map_err(|_| Error::<T>::MaxModelsPerOwnerExceeded)?;
			OwnerModels::<T>::insert(&owner, owner_models);

			Self::deposit_event(Event::ModelRegistered {
				model_id,
				owner,
			});

			Ok(())
		}

		/// Update model configuration
		#[pallet::call_index(1)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn update_model(
			origin: OriginFor<T>,
			model_id: u32,
			endpoint: Option<BoundedVec<u8, ConstU32<256>>>,
			temperature: Option<u16>,
			max_tokens: Option<u32>,
			seed: Option<u32>,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			// Get and verify model ownership
			let mut model = Models::<T>::get(model_id).ok_or(Error::<T>::ModelNotFound)?;
			ensure!(model.owner == who, Error::<T>::NotModelOwner);

			// Update fields if provided
			if let Some(ep) = endpoint {
				model.endpoint = ep;
			}
			if let Some(temp) = temperature {
				ensure!(temp <= 2000, Error::<T>::InvalidTemperature);
				model.default_temperature = temp;
			}
			if let Some(tokens) = max_tokens {
				model.default_max_tokens = tokens;
			}
			if let Some(s) = seed {
				model.default_seed = s;
			}

			// Update timestamp
			let current_block = <polkadot_sdk::frame_system::Pallet<T>>::block_number();
			model.updated_at = TryInto::<u32>::try_into(current_block).unwrap_or(0);

			// Save updated model
			Models::<T>::insert(model_id, model);

			Self::deposit_event(Event::ModelUpdated { model_id, owner: who });

			Ok(())
		}

		/// Toggle model active status
		#[pallet::call_index(2)]
		#[pallet::weight(Weight::from_parts(10_000, 0))]
		pub fn toggle_model_status(
			origin: OriginFor<T>,
			model_id: u32,
		) -> DispatchResult {
			let who = ensure_signed(origin)?;

			// Get and verify model ownership
			let mut model = Models::<T>::get(model_id).ok_or(Error::<T>::ModelNotFound)?;
			ensure!(model.owner == who, Error::<T>::NotModelOwner);

			// Toggle status
			model.is_active = !model.is_active;

			// Update timestamp
			let current_block = <polkadot_sdk::frame_system::Pallet<T>>::block_number();
			model.updated_at = TryInto::<u32>::try_into(current_block).unwrap_or(0);

			let is_active = model.is_active;

			// Save updated model
			Models::<T>::insert(model_id, model);

			Self::deposit_event(Event::ModelStatusChanged {
				model_id,
				is_active,
			});

			Ok(())
		}
	}

	// Helper functions
	impl<T: Config> Pallet<T> {
		/// Get model configuration by ID
		pub fn get_model(model_id: u32) -> Option<ModelConfig<T::AccountId>> {
			Models::<T>::get(model_id)
		}

		/// Check if a model is usable (active status)
		pub fn is_model_active(model_id: u32) -> bool {
			Models::<T>::get(model_id)
				.map(|m| m.is_active)
				.unwrap_or(false)
		}
	}
}