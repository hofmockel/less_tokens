"""Sample module for testing the Python chunker."""

MY_CONSTANT = 42
ANOTHER_CONSTANT = "hello"
THRESHOLD: int = 100


def simple_function(x):
    """Return double x."""
    return x * 2


def another_function(a, b):
    """Return sum of a and b."""
    return a + b


def third_function():
    """Return a string."""
    return "three"


def fourth_function(items):
    """Filter items above threshold."""
    return [i for i in items if i > THRESHOLD]


def fifth_function():
    pass


def sixth_function(x, y, z):
    return x + y + z


async def async_function():
    """Async no-op."""
    pass


class MyClass:
    """A sample class with two methods."""

    CLASS_ATTR = "class_level"

    def method_one(self):
        """First method."""
        return self.CLASS_ATTR

    def method_two(self, x):
        """Second method."""
        return x * 2


class AnotherClass:
    """Second class for coverage."""

    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value
