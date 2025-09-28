// This file is part of Substrate.

// Copyright (C) Parity Technologies (UK) Ltd.
// SPDX-License-Identifier: Apache-2.0

// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// 	http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

use polkadot_sdk::{sc_cli::RunCmd, *};

#[derive(Debug, Clone)]
pub enum NodeRole {
	/// ML Worker node that processes inference requests
	Worker,
	/// Validator node that verifies inference results
	Validator,
	/// Both Worker and Validator - processes requests and validates others
	WorkerValidator,
}

impl std::str::FromStr for NodeRole {
	type Err = String;

	fn from_str(s: &str) -> Result<Self, Self::Err> {
		match s.to_lowercase().as_str() {
			"worker" => Ok(NodeRole::Worker),
			"validator" => Ok(NodeRole::Validator),
			"worker-validator" | "both" => Ok(NodeRole::WorkerValidator),
			_ => Err("Invalid node role. Must be: worker, validator, or worker-validator".into()),
		}
	}
}

#[derive(Debug, Clone)]
pub enum Consensus {
	ManualSeal(u64),
	InstantSeal,
	None,
}

impl std::str::FromStr for Consensus {
	type Err = String;

	fn from_str(s: &str) -> Result<Self, Self::Err> {
		Ok(if s == "instant-seal" {
			Consensus::InstantSeal
		} else if let Some(block_time) = s.strip_prefix("manual-seal-") {
			Consensus::ManualSeal(block_time.parse().map_err(|_| "invalid block time")?)
		} else if s.to_lowercase() == "none" {
			Consensus::None
		} else {
			return Err("incorrect consensus identifier".into());
		})
	}
}

#[derive(Debug, clap::Parser)]
pub struct Cli {
	#[command(subcommand)]
	pub subcommand: Option<Subcommand>,

	#[clap(long, default_value = "manual-seal-3000")]
	pub consensus: Consensus,

	/// The role of this node (worker, validator, or worker-validator)
	#[clap(long, default_value = "worker")]
	pub node_role: NodeRole,

	/// AI API endpoint (OpenAI-compatible API)
	#[clap(long, default_value = "http://localhost:11434")]
	pub ai_endpoint: String,

	/// AI API key (optional)
	#[clap(long, env = "AI_API_KEY")]
	pub ai_api_key: Option<String>,

	/// AI model to use (e.g., gpt-4, gemma:2b, mistral:7b)
	#[clap(long, default_value = "gemma3:1b")]
	pub ai_model: String,

	#[clap(flatten)]
	pub run: RunCmd,
}

#[derive(Debug, clap::Subcommand)]
pub enum Subcommand {
	/// Key management cli utilities
	#[command(subcommand)]
	Key(sc_cli::KeySubcommand),

	/// Build a chain specification.
	BuildSpec(sc_cli::BuildSpecCmd),

	/// Validate blocks.
	CheckBlock(sc_cli::CheckBlockCmd),

	/// Export blocks.
	ExportBlocks(sc_cli::ExportBlocksCmd),

	/// Export the state of a given block into a chain spec.
	ExportState(sc_cli::ExportStateCmd),

	/// Import blocks.
	ImportBlocks(sc_cli::ImportBlocksCmd),

	/// Remove the whole chain.
	PurgeChain(sc_cli::PurgeChainCmd),

	/// Revert the chain to a previous state.
	Revert(sc_cli::RevertCmd),

	/// Db meta columns information.
	ChainInfo(sc_cli::ChainInfoCmd),
}
