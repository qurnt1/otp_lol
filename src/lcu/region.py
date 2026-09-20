"""LCU region helpers kept as a stable import path."""

from ..config.regions import (
    RegionIdentity,
    detect_account_routing,
    normalize_platform_id,
    normalize_provider_region,
    normalize_region_identity,
    platform_to_provider_region,
    platform_to_regional_routing,
)

__all__ = ["RegionIdentity", "detect_account_routing", "normalize_platform_id", "normalize_provider_region", "normalize_region_identity", "platform_to_provider_region", "platform_to_regional_routing"]
