//! # QX KILT Permissions Pallet
//!
//! This pallet manages KILT-based permissions for AI workers.

#![cfg_attr(not(feature = "std"), no_std)]

use codec::{Decode, Encode, MaxEncodedLen};
use polkadot_sdk::frame_support::{
    dispatch::DispatchResult,
    pallet_prelude::*,
    traits::{Currency, ReservableCurrency},
};
use polkadot_sdk::frame_system::pallet_prelude::*;
use scale_info::TypeInfo;
use polkadot_sdk::sp_runtime::{
    traits::{Hash, Saturating},
    DispatchError, RuntimeDebug,
};
use polkadot_sdk::sp_std::prelude::*;

pub use pallet::*;

/// DID identifier type
pub type DidIdentifier = [u8; 32];

/// Model ID type
pub type ModelId = u32;

/// Worker metadata
#[derive(Clone, Encode, Decode, Eq, PartialEq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct WorkerMetadata<BlockNumber> {
    pub name: BoundedVec<u8, ConstU32<128>>,
    pub description: BoundedVec<u8, ConstU32<512>>,
    pub registered_at: BlockNumber,
}

/// Worker DID information
#[derive(Clone, Encode, Decode, Eq, PartialEq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct WorkerDID<AccountId, BlockNumber> {
    pub did: DidIdentifier,
    pub account: AccountId,
    pub metadata: WorkerMetadata<BlockNumber>,
    pub status: CredentialStatus<BlockNumber>,
}

/// Credential status
#[derive(Clone, Encode, Decode, Eq, PartialEq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub enum CredentialStatus<BlockNumber> {
    Active,
    Suspended { until: BlockNumber },
    Revoked,
}

/// AI Worker Credential
#[derive(Clone, Encode, Decode, Eq, PartialEq, RuntimeDebug, TypeInfo, MaxEncodedLen)]
pub struct AIWorkerCredential<BlockNumber> {
    pub issuer: DidIdentifier,  // QX Chain governance DID
    pub subject: DidIdentifier, // Worker DID
    pub models: BoundedVec<ModelId, ConstU32<100>>,
    pub issued_at: BlockNumber,
    pub expires_at: Option<BlockNumber>,
}

#[polkadot_sdk::frame_support::pallet]
pub mod pallet {
    use super::*;

    #[pallet::pallet]
    pub struct Pallet<T>(_);

    #[pallet::config]
    pub trait Config: polkadot_sdk::frame_system::Config {
        type RuntimeEvent: From<Event<Self>> + IsType<<Self as polkadot_sdk::frame_system::Config>::RuntimeEvent>;

        type Currency: Currency<Self::AccountId> + ReservableCurrency<Self::AccountId>;

        /// Default credential validity period
        #[pallet::constant]
        type DefaultCredentialValidity: Get<BlockNumberFor<Self>>;

        /// Worker suspension period
        #[pallet::constant]
        type WorkerSuspensionPeriod: Get<BlockNumberFor<Self>>;
    }

    // Storage

    /// Worker DIDs mapped by account
    #[pallet::storage]
    #[pallet::getter(fn worker_dids)]
    pub type WorkerDIDs<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        T::AccountId,
        WorkerDID<T::AccountId, BlockNumberFor<T>>,
    >;

    /// Worker credentials mapped by DID
    #[pallet::storage]
    #[pallet::getter(fn worker_credentials)]
    pub type WorkerCredentials<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        DidIdentifier,
        AIWorkerCredential<BlockNumberFor<T>>,
    >;

    /// Account to DID mapping for reverse lookup
    #[pallet::storage]
    #[pallet::getter(fn account_to_did)]
    pub type AccountToDID<T: Config> = StorageMap<
        _,
        Blake2_128Concat,
        T::AccountId,
        DidIdentifier,
    >;

    /// Governance DID (issuer for all system credentials)
    #[pallet::storage]
    #[pallet::getter(fn governance_did)]
    pub type GovernanceDID<T: Config> = StorageValue<_, DidIdentifier, ValueQuery>;

    // Events

    #[pallet::event]
    #[pallet::generate_deposit(pub(super) fn deposit_event)]
    pub enum Event<T: Config> {
        /// Worker DID created
        WorkerDIDCreated {
            account: T::AccountId,
            did: DidIdentifier,
        },

        /// Worker credential issued
        WorkerCredentialIssued {
            did: DidIdentifier,
            expires_at: Option<BlockNumberFor<T>>,
        },

        /// Worker credential revoked
        WorkerCredentialRevoked {
            did: DidIdentifier,
        },

        /// Worker suspended
        WorkerSuspended {
            did: DidIdentifier,
            until: BlockNumberFor<T>,
        },

        /// Governance DID set
        GovernanceDIDSet {
            did: DidIdentifier,
        },
    }

    // Errors

    #[pallet::error]
    pub enum Error<T> {
        /// Worker DID already exists
        WorkerDIDAlreadyExists,
        /// Worker DID not found
        WorkerDIDNotFound,
        /// Worker credential not found
        WorkerCredentialNotFound,
        /// Invalid credential issuer
        InvalidCredentialIssuer,
        /// Credential expired
        CredentialExpired,
        /// Credential suspended
        CredentialSuspended,
        /// Credential revoked
        CredentialRevoked,
        /// Not authorized to issue credentials
        NotAuthorizedToIssue,
        /// Not authorized to revoke credentials
        NotAuthorizedToRevoke,
        /// Governance DID not set
        GovernanceDIDNotSet,
        /// Account has no DID
        AccountHasNoDID,
        /// Invalid bounded vec conversion
        InvalidBoundedVec,
    }

    // Extrinsics

    #[pallet::call]
    impl<T: Config> Pallet<T> {
        /// Initialize governance DID (sudo only)
        #[pallet::call_index(0)]
        #[pallet::weight(10_000)]
        pub fn set_governance_did(
            origin: OriginFor<T>,
            did: DidIdentifier,
        ) -> DispatchResult {
            ensure_root(origin)?;

            GovernanceDID::<T>::put(&did);

            Self::deposit_event(Event::GovernanceDIDSet { did });
            Ok(())
        }

        /// Create a worker DID
        #[pallet::call_index(1)]
        #[pallet::weight(10_000)]
        pub fn create_worker_did(
            origin: OriginFor<T>,
            name: Vec<u8>,
            description: Vec<u8>,
        ) -> DispatchResult {
            let who = ensure_signed(origin)?;

            ensure!(
                !WorkerDIDs::<T>::contains_key(&who),
                Error::<T>::WorkerDIDAlreadyExists
            );

            // Generate DID from account
            let did = Self::generate_did(&who);

            let worker_did = WorkerDID {
                did,
                account: who.clone(),
                metadata: WorkerMetadata {
                    name: BoundedVec::try_from(name).map_err(|_| Error::<T>::InvalidBoundedVec)?,
                    description: BoundedVec::try_from(description).map_err(|_| Error::<T>::InvalidBoundedVec)?,
                    registered_at: polkadot_sdk::frame_system::Pallet::<T>::block_number(),
                },
                status: CredentialStatus::Active,
            };

            WorkerDIDs::<T>::insert(&who, &worker_did);
            AccountToDID::<T>::insert(&who, &did);

            Self::deposit_event(Event::WorkerDIDCreated {
                account: who,
                did,
            });

            Ok(())
        }

        /// Issue worker credential (sudo only)
        #[pallet::call_index(2)]
        #[pallet::weight(10_000)]
        pub fn issue_worker_credential(
            origin: OriginFor<T>,
            worker_did: DidIdentifier,
            models: Vec<ModelId>,
            validity_period: Option<BlockNumberFor<T>>,
        ) -> DispatchResult {
            ensure_root(origin)?;

            // Get governance DID (all zeros means "system/governance")
            let governance_did = GovernanceDID::<T>::get();

            let current_block = polkadot_sdk::frame_system::Pallet::<T>::block_number();
            let expires_at = validity_period.map(|period| current_block.saturating_add(period));

            let credential = AIWorkerCredential {
                issuer: governance_did,
                subject: worker_did,
                models: BoundedVec::try_from(models).map_err(|_| Error::<T>::InvalidBoundedVec)?,
                issued_at: current_block,
                expires_at,
            };

            WorkerCredentials::<T>::insert(&worker_did, &credential);

            Self::deposit_event(Event::WorkerCredentialIssued {
                did: worker_did,
                expires_at,
            });

            Ok(())
        }

        /// Revoke worker credential (sudo only)
        #[pallet::call_index(3)]
        #[pallet::weight(10_000)]
        pub fn revoke_worker_credential(
            origin: OriginFor<T>,
            worker_did: DidIdentifier,
        ) -> DispatchResult {
            ensure_root(origin)?;

            WorkerCredentials::<T>::remove(&worker_did);

            Self::deposit_event(Event::WorkerCredentialRevoked {
                did: worker_did,
            });

            Ok(())
        }

        /// Suspend worker (sudo only)
        #[pallet::call_index(4)]
        #[pallet::weight(10_000)]
        pub fn suspend_worker(
            origin: OriginFor<T>,
            worker_did: DidIdentifier,
            duration: Option<BlockNumberFor<T>>,
        ) -> DispatchResult {
            ensure_root(origin)?;

            let current_block = polkadot_sdk::frame_system::Pallet::<T>::block_number();
            let until = current_block.saturating_add(
                duration.unwrap_or(T::WorkerSuspensionPeriod::get())
            );

            // Update worker DID status - iterate through all workers to find the one with matching DID
            for (account, mut worker_did_info) in WorkerDIDs::<T>::iter() {
                if worker_did_info.did == worker_did {
                    worker_did_info.status = CredentialStatus::Suspended { until };
                    WorkerDIDs::<T>::insert(&account, worker_did_info);
                    break;
                }
            }

            Self::deposit_event(Event::WorkerSuspended {
                did: worker_did,
                until,
            });

            Ok(())
        }
    }

    // Helper functions
    impl<T: Config> Pallet<T> {
        /// Generate DID from account
        pub fn generate_did(account: &T::AccountId) -> DidIdentifier {
            let mut did = [0u8; 32];
            let hash = T::Hashing::hash_of(account);
            let hash_bytes = hash.as_ref();
            let len = hash_bytes.len().min(32);
            did[..len].copy_from_slice(&hash_bytes[..len]);
            did
        }

        /// Verify worker credential
        pub fn verify_worker_credential(worker_did: &DidIdentifier) -> Result<bool, DispatchError> {
            let credential = WorkerCredentials::<T>::get(worker_did)
                .ok_or(Error::<T>::WorkerCredentialNotFound)?;

            let current_block = polkadot_sdk::frame_system::Pallet::<T>::block_number();

            // Check expiry
            if let Some(expires_at) = credential.expires_at {
                if current_block > expires_at {
                    return Ok(false);
                }
            }

            // Check worker status
            for (_, worker_did_info) in WorkerDIDs::<T>::iter() {
                if worker_did_info.did == *worker_did {
                    match worker_did_info.status {
                        CredentialStatus::Active => return Ok(true),
                        CredentialStatus::Suspended { until } => {
                            if current_block > until {
                                return Ok(true); // Suspension expired
                            }
                            return Ok(false);
                        }
                        CredentialStatus::Revoked => return Ok(false),
                    }
                }
            }

            Ok(true)
        }

        /// Get worker DID from account
        pub fn get_worker_did(account: &T::AccountId) -> Result<DidIdentifier, DispatchError> {
            AccountToDID::<T>::get(account)
                .ok_or(Error::<T>::AccountHasNoDID.into())
        }

        /// Suspend worker credential
        pub fn suspend_worker_credential(
            worker_did: &DidIdentifier,
            duration: BlockNumberFor<T>,
        ) -> DispatchResult {
            let current_block = polkadot_sdk::frame_system::Pallet::<T>::block_number();
            let until = current_block.saturating_add(duration);

            // Update worker DID status
            for (account, mut worker_did_info) in WorkerDIDs::<T>::iter() {
                if worker_did_info.did == *worker_did {
                    worker_did_info.status = CredentialStatus::Suspended { until };
                    WorkerDIDs::<T>::insert(&account, worker_did_info);
                    break;
                }
            }

            Self::deposit_event(Event::WorkerSuspended {
                did: *worker_did,
                until,
            });

            Ok(())
        }
    }
}