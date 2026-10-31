"""Public affect interface; emotion.py remains the compatibility implementation."""

from .emotion import normalize_state, transition, response_policy, affect_summary

__all__ = ["normalize_state", "transition", "response_policy", "affect_summary"]
