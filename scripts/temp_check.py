#!/usr/bin/env python3

from substrateinterface import SubstrateInterface

substrate = SubstrateInterface(url="ws://localhost:9944")

min_stake = substrate.get_constant("QxAi", "MinWorkerStake")

print(f"Minimum Worker Stake: {min_stake}")
