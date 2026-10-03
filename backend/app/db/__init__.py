"""MongoDB access layer.

Only the connection wiring lives here. Business collections are added in a
later step. The connection string is held in a ``SecretStr`` and is never
logged or returned to a client.
"""
