"""Standalone, conditional SRAM-to-FFN-weight consumption contracts."""

from .model import ContractConfig, ContractError, candidate_config, simulate, validate

__all__ = ["ContractConfig", "ContractError", "candidate_config", "simulate", "validate"]
