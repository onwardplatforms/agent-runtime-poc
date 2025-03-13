import math
from typing import Annotated

from semantic_kernel.functions.kernel_function_decorator import kernel_function


class MathPlugin:
    """Description: MathPlugin provides a set of functions to make Math calculations.

    Usage:
        kernel.add_plugin(MathPlugin(), plugin_name="math")

    Examples:
        {{math.Add}} => Returns the sum of input and amount
        {{math.Subtract}} => Returns the difference of input and amount
        {{math.Multiply}} => Returns the product of input and amount
        {{math.Divide}} => Returns the quotient of input and amount
        {{math.SquareRoot}} => Returns the square root of input
        {{math.Log}} => Returns the logarithm of input with optional base
    """

    @kernel_function(name="Add", description="Adds two numbers together.")
    def add(
        self,
        input: Annotated[float, "the first number to add"],
        amount: Annotated[float, "the second number to add"],
    ) -> Annotated[float, "the sum of the two numbers"]:
        """Returns the addition result of the values provided."""
        print(f"ƒ(x) calling add({input}, {amount})")
        if isinstance(input, str):
            input = float(input)
        if isinstance(amount, str):
            amount = float(amount)
        return input + amount

    @kernel_function(name="Subtract", description="Subtracts the second number from the first.")
    def subtract(
        self,
        input: Annotated[float, "the first number"],
        amount: Annotated[float, "the number to subtract"],
    ) -> Annotated[float, "the difference between the two numbers"]:
        """Returns the difference of numbers provided."""
        print(f"ƒ(x) calling subtract({input}, {amount})")
        if isinstance(input, str):
            input = float(input)
        if isinstance(amount, str):
            amount = float(amount)
        return input - amount

    @kernel_function(name="Multiply", description="Multiplies two numbers together.")
    def multiply(
        self,
        input: Annotated[float, "the first number to multiply"],
        amount: Annotated[float, "the second number to multiply"],
    ) -> Annotated[float, "the product of the two numbers"]:
        """Returns the product of the values provided."""
        print(f"ƒ(x) calling multiply({input}, {amount})")
        if isinstance(input, str):
            input = float(input)
        if isinstance(amount, str):
            amount = float(amount)
        return input * amount

    @kernel_function(name="Divide", description="Divides the first number by the second.")
    def divide(
        self,
        input: Annotated[float, "the number to be divided"],
        amount: Annotated[float, "the number to divide by"],
    ) -> Annotated[float, "the quotient of the division"]:
        """Returns the quotient of the division."""
        print(f"ƒ(x) calling divide({input}, {amount})")
        if isinstance(input, str):
            input = float(input)
        if isinstance(amount, str):
            amount = float(amount)
        
        if amount == 0:
            raise ValueError("Cannot divide by zero.")
        
        return input / amount

    @kernel_function(name="SquareRoot", description="Calculates the square root of a number.")
    def square_root(
        self,
        input: Annotated[float, "the number to find the square root of"],
    ) -> Annotated[float, "the square root of the number"]:
        """Returns the square root of the value provided."""
        print(f"ƒ(x) calling square_root({input})")
        if isinstance(input, str):
            input = float(input)
        
        if input < 0:
            raise ValueError("Cannot calculate square root of a negative number.")
        
        import math
        return math.sqrt(input)

    @kernel_function(name="Power", description="Raises a number to the power of another.")
    def power(
        self,
        input: Annotated[float, "the base number"],
        exponent: Annotated[float, "the exponent to raise the base to"],
    ) -> Annotated[float, "the result of the exponentiation"]:
        """Returns the base raised to the power of the exponent."""
        print(f"ƒ(x) calling power({input}, {exponent})")
        if isinstance(input, str):
            input = float(input)
        if isinstance(exponent, str):
            exponent = float(exponent)
        
        return input ** exponent 

    @kernel_function(name="Log", description="Calculates the logarithm of a number with an optional base (defaults to natural log).")
    def log(
        self,
        input: Annotated[float, "the number to calculate the logarithm of"],
        base: Annotated[float, "the base of the logarithm (optional, defaults to e for natural log)"] = math.e,
    ) -> Annotated[float, "the logarithm of the input"]:
        """Returns the logarithm of the input with the specified base (defaults to natural log)."""
        print(f"ƒ(x) calling log({input}, base={base})")
        if isinstance(input, str):
            input = float(input)
        if isinstance(base, str):
            base = float(base)
        
        if input <= 0:
            raise ValueError("Cannot calculate logarithm of a non-positive number.")
        if base <= 0 or base == 1:
            raise ValueError("Logarithm base must be positive and not equal to 1.")
        
        if base == math.e:
            return math.log(input)  # Natural logarithm
        else:
            return math.log(input, base)  # Logarithm with custom base 
        
    @kernel_function(name="Modulo", description="Finds the remainder of division of one number by another.")
    def modulo(
        self,
        input: Annotated[int, "the number to be divided"],
        amount: Annotated[int, "the divisor"],
    ) -> Annotated[int, "the remainder of the division"]:
        """Returns the remainder of division."""
        print(f"ƒ(x) calling modulo({input}, {amount})")
        if amount == 0:
            raise ValueError("Cannot modulo by zero.")
        return input % amount
    
    @kernel_function(name="ModularInverse", description="Finds the modular inverse of a number modulo another number.")
    def modular_inverse(
        self,
        input: Annotated[int, "the number to find the modular inverse of"],
        modulus: Annotated[int, "the modulus"],
    ) -> Annotated[int, "the modular inverse of the number modulo the given modulus"]:
        """Returns the modular inverse of input modulo modulus using brute-force search."""
        print(f"ƒ(x) calling modular_inverse({input}, {modulus})")

        # Ensure input is within modulo range
        input = input % modulus
        
        # Brute force search for modular inverse
        for x in range(1, modulus):
            if (input * x) % modulus == 1:
                return x

        raise ValueError(f"No modular inverse exists for {input} mod {modulus}.")
