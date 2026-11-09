"""Numbers as the page shows them."""

import math


def shown(value: float) -> int:
    """
    A number rounded the way the page rounds it (JavaScript's Math.round: halves go up).
    
    Text written here sits beside figures the page rounds itself. Python's round()
    sends halves to the even number, so 22.5°C would read 22 here and 23 there.
    """
    return math.floor(value + 0.5)
