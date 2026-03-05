"""Meta-Agent Plugin Optimization System for SunnyAgent.

This system uses Claude Agent Team architecture to automatically optimize
Plugin Commands and Skills in the packages/ directory through iterative
evaluation using Langfuse.
"""

__version__ = "0.1.0"
__author__ = "SunnyAgent Team"

from meta_agent.config import load_config, OptimizationConfig

__all__ = [
    "__version__",
    "load_config",
    "OptimizationConfig",
]
