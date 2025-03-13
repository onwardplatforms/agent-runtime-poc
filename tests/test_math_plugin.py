import math
import pytest
from agents.math_agent.plugins.math_plugin import MathPlugin

@pytest.fixture
def math_plugin():
    """Create a MathPlugin instance for testing."""
    return MathPlugin()

def test_add(math_plugin):
    """Test the add function."""
    assert math_plugin.add(2, 3) == 5.0
    assert math_plugin.add(-1, 1) == 0.0
    assert math_plugin.add(0, 0) == 0.0
    assert math_plugin.add("2", "3") == 5.0  # Test string inputs
    assert math_plugin.add(2.5, 3.7) == 6.2

def test_subtract(math_plugin):
    """Test the subtract function."""
    assert math_plugin.subtract(5, 3) == 2.0
    assert math_plugin.subtract(1, 1) == 0.0
    assert math_plugin.subtract(0, 0) == 0.0
    assert math_plugin.subtract("5", "3") == 2.0  # Test string inputs
    assert math_plugin.subtract(5.5, 2.2) == 3.3
    assert math_plugin.subtract(3, 5) == -2.0  # Test negative result

def test_multiply(math_plugin):
    """Test the multiply function."""
    assert math_plugin.multiply(2, 3) == 6.0
    assert math_plugin.multiply(-2, 3) == -6.0
    assert math_plugin.multiply(-2, -3) == 6.0
    assert math_plugin.multiply(0, 5) == 0.0
    assert math_plugin.multiply("2", "3") == 6.0  # Test string inputs
    assert math_plugin.multiply(2.5, 2) == 5.0

def test_divide(math_plugin):
    """Test the divide function."""
    assert math_plugin.divide(6, 2) == 3.0
    assert math_plugin.divide(5, 2) == 2.5
    assert math_plugin.divide(-6, 2) == -3.0
    assert math_plugin.divide(0, 5) == 0.0
    assert math_plugin.divide("6", "2") == 3.0  # Test string inputs
    
    # Test division by zero error
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        math_plugin.divide(5, 0)

def test_square_root(math_plugin):
    """Test the square_root function."""
    assert math_plugin.square_root(4) == 2.0
    assert math_plugin.square_root(0) == 0.0
    assert math_plugin.square_root(2) == pytest.approx(1.4142135623730951)
    assert math_plugin.square_root("4") == 2.0  # Test string input
    
    # Test negative number error
    with pytest.raises(ValueError, match="Cannot calculate square root of a negative number"):
        math_plugin.square_root(-4)

def test_power(math_plugin):
    """Test the power function."""
    assert math_plugin.power(2, 3) == 8.0
    assert math_plugin.power(2, 0) == 1.0
    assert math_plugin.power(2, -1) == 0.5
    assert math_plugin.power(0, 5) == 0.0
    assert math_plugin.power("2", "3") == 8.0  # Test string inputs
    assert math_plugin.power(2, 0.5) == pytest.approx(1.4142135623730951)  # Square root

def test_log(math_plugin):
    """Test the log function."""
    # Test natural logarithm (base e)
    assert math_plugin.log(math.e) == pytest.approx(1.0)
    assert math_plugin.log(1) == pytest.approx(0.0)
    assert math_plugin.log("2.718281828459045") == pytest.approx(1.0)  # Test string input
    
    # Test custom base logarithm
    assert math_plugin.log(100, 10) == pytest.approx(2.0)  # log_10(100) = 2
    assert math_plugin.log(8, 2) == pytest.approx(3.0)     # log_2(8) = 3
    
    # Test error cases
    with pytest.raises(ValueError, match="Cannot calculate logarithm of a non-positive number"):
        math_plugin.log(0)
    
    with pytest.raises(ValueError, match="Cannot calculate logarithm of a non-positive number"):
        math_plugin.log(-1)
    
    with pytest.raises(ValueError, match="Logarithm base must be positive and not equal to 1"):
        math_plugin.log(2, 0)
    
    with pytest.raises(ValueError, match="Logarithm base must be positive and not equal to 1"):
        math_plugin.log(2, 1)
    
    with pytest.raises(ValueError, match="Logarithm base must be positive and not equal to 1"):
        math_plugin.log(2, -1)

def test_type_conversions(math_plugin):
    """Test that all functions properly handle string inputs."""
    assert math_plugin.add("2.5", "3.5") == 6.0
    assert math_plugin.subtract("5.5", "2.2") == 3.3
    assert math_plugin.multiply("2.5", "2") == 5.0
    assert math_plugin.divide("5", "2") == 2.5
    assert math_plugin.square_root("16") == 4.0
    assert math_plugin.power("2", "3") == 8.0
    assert math_plugin.log("2.718281828459045") == pytest.approx(1.0)

def test_floating_point_precision(math_plugin):
    """Test that functions handle floating point numbers with appropriate precision."""
    assert math_plugin.add(1.23456789, 2.34567890) == pytest.approx(3.58024679)
    assert math_plugin.multiply(1.23456789, 2) == pytest.approx(2.46913578)
    assert math_plugin.divide(1, 3) == pytest.approx(0.333333333)
    assert math_plugin.power(2, 0.5) == pytest.approx(1.4142135623730951)
    assert math_plugin.log(2.718281828459045) == pytest.approx(1.0) 