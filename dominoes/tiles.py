from .types import Domino

def generate_full_set(max_pip: int = 6) -> list[Domino]:
    """Generate a full set of dominoes up to the specified max pip value."""
    return [Domino(left, right) for left in range(max_pip + 1) for right in range(left, max_pip + 1)]