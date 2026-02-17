from .types import Domino


def generate_double_six_set() -> list[Domino]:
    return [Domino(i, j) for i in range(7) for j in range(i, 7)]
