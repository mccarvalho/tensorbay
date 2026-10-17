"""Directory domain: read-only people lookup backed by the Cognito user pool.

Exposes a minimal {sub, email, name} list so internal users can pick an
account owner (and similar) without the privileged admin scope.
"""
