"""Business logic. Route handlers (and Phase 2 agent tools) call these functions."""


class NotFoundError(Exception):
    """Raised when a record does not exist or is not owned by the current user."""

    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found")
        self.resource = resource
