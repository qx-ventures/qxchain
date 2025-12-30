//! QX Faucet pallet - Token distribution for user onboarding
//!
//! This pallet allows new users to claim tokens for free to get started
//! with the QX Chain. Rate-limited and capped per account.

#![cfg_attr(not(feature = "std"), no_std)]

extern crate alloc;

use frame::prelude::*;
use polkadot_sdk::polkadot_sdk_frame as frame;

use frame::deps::frame_support::dispatch::{DispatchClass, Pays};
use frame::traits::{Currency, ExistenceRequirement};

pub use pallet::*;

/// Balance type alias
type BalanceOf<T> = <<T as Config>::Currency as Currency<<T as frame_system::Config>::AccountId>>::Balance;

#[frame::pallet]
pub mod pallet {
	use super::*;

	#[pallet::config]
	pub trait Config: polkadot_sdk::frame_system::Config {
		type RuntimeEvent: From<Event<Self>> + IsType<<Self as polkadot_sdk::frame_system::Config>::RuntimeEvent>;

		/// The currency trait for handling token operations
		type Currency: Currency<Self::AccountId>;

		/// Amount dispensed per claim
		#[pallet::constant]
		type DripAmount: Get<BalanceOf<Self>>;

		/// Minimum blocks between claims
		#[pallet::constant]
		type ClaimCooldown: Get<BlockNumberFor<Self>>;

		/// Maximum total claims per account (lifetime)
		#[pallet::constant]
		type MaxClaimsPerAccount: Get<u32>;

		/// The faucet pot account that holds tokens to distribute
		type FaucetPot: Get<Self::AccountId>;
	}

	#[pallet::pallet]
	pub struct Pallet<T>(_);

	/// Last claim block for each account
	#[pallet::storage]
	pub type LastClaim<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, BlockNumberFor<T>>;

	/// Total claims made by each account
	#[pallet::storage]
	pub type ClaimCount<T: Config> = StorageMap<_, Blake2_128Concat, T::AccountId, u32, ValueQuery>;

	/// Events emitted by the pallet
	#[pallet::event]
	#[pallet::generate_deposit(pub(super) fn deposit_event)]
	pub enum Event<T: Config> {
		/// Tokens claimed from faucet
		Claimed {
			who: T::AccountId,
			amount: BalanceOf<T>,
		},
		/// Faucet pot funded
		FaucetFunded {
			funder: T::AccountId,
			amount: BalanceOf<T>,
		},
	}

	/// Errors that can be returned by this pallet
	#[pallet::error]
	pub enum Error<T> {
		/// Claim attempted too soon after previous claim
		ClaimTooSoon,
		/// Maximum lifetime claims reached
		MaxClaimsReached,
		/// Faucet pot has insufficient balance
		FaucetEmpty,
	}

	#[pallet::call]
	impl<T: Config> Pallet<T> {
		/// Claim tokens from the faucet
		///
		/// This is a FREE transaction (Pays::No) so users don't need
		/// existing balance to claim their first tokens.
		#[pallet::call_index(0)]
		#[pallet::weight((Weight::from_parts(50_000, 0), DispatchClass::Normal, Pays::No))]
		pub fn claim(origin: OriginFor<T>) -> DispatchResult {
			let who = ensure_signed(origin)?;

			let current_block = frame_system::Pallet::<T>::block_number();

			// Check cooldown
			if let Some(last) = LastClaim::<T>::get(&who) {
				let cooldown = T::ClaimCooldown::get();
				ensure!(
					current_block >= last.saturating_add(cooldown),
					Error::<T>::ClaimTooSoon
				);
			}

			// Check max claims
			let claims = ClaimCount::<T>::get(&who);
			ensure!(claims < T::MaxClaimsPerAccount::get(), Error::<T>::MaxClaimsReached);

			let drip_amount = T::DripAmount::get();
			let faucet_pot = T::FaucetPot::get();

			// Check faucet has sufficient balance
			let faucet_balance = T::Currency::free_balance(&faucet_pot);
			ensure!(faucet_balance >= drip_amount, Error::<T>::FaucetEmpty);

			// Transfer from faucet pot to claimer
			T::Currency::transfer(
				&faucet_pot,
				&who,
				drip_amount,
				ExistenceRequirement::KeepAlive,
			)?;

			// Update state
			LastClaim::<T>::insert(&who, current_block);
			ClaimCount::<T>::mutate(&who, |c| *c = c.saturating_add(1));

			Self::deposit_event(Event::Claimed { who, amount: drip_amount });

			Ok(())
		}

		/// Fund the faucet pot (anyone can contribute)
		#[pallet::call_index(1)]
		#[pallet::weight(Weight::from_parts(50_000, 0))]
		pub fn fund_faucet(origin: OriginFor<T>, amount: BalanceOf<T>) -> DispatchResult {
			let who = ensure_signed(origin)?;
			let faucet_pot = T::FaucetPot::get();

			T::Currency::transfer(
				&who,
				&faucet_pot,
				amount,
				ExistenceRequirement::KeepAlive,
			)?;

			Self::deposit_event(Event::FaucetFunded { funder: who, amount });

			Ok(())
		}
	}

	impl<T: Config> Pallet<T> {
		/// Get remaining claims for an account
		pub fn remaining_claims(account: &T::AccountId) -> u32 {
			let claims = ClaimCount::<T>::get(account);
			T::MaxClaimsPerAccount::get().saturating_sub(claims)
		}

		/// Get faucet balance
		pub fn faucet_balance() -> BalanceOf<T> {
			T::Currency::free_balance(&T::FaucetPot::get())
		}

		/// Check if account can claim now
		pub fn can_claim(account: &T::AccountId) -> bool {
			// Check max claims
			if ClaimCount::<T>::get(account) >= T::MaxClaimsPerAccount::get() {
				return false;
			}

			// Check cooldown
			if let Some(last) = LastClaim::<T>::get(account) {
				let current_block = frame_system::Pallet::<T>::block_number();
				let cooldown = T::ClaimCooldown::get();
				if current_block < last.saturating_add(cooldown) {
					return false;
				}
			}

			// Check faucet has funds
			let drip_amount = T::DripAmount::get();
			T::Currency::free_balance(&T::FaucetPot::get()) >= drip_amount
		}
	}
}
