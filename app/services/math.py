import math


class MathService:
    def next_power_of_two(self, number: float):
        return 1 if number == 0 else 2 ** math.ceil(math.log2(number))
