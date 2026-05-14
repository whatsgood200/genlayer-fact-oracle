# { "Depends": "py-genlayer:test" }
# Exact pattern from the working GenLayer tutorial
# Only uses str, int, bool — no dict, no Address, no TreeMap
# If this deploys without error, the issue in our main contract
# is the dict/Address type mismatch

from genlayer import *

class HelloWorld(gl.Contract):
    greeting: str
    count:    int
    active:   bool

    def __init__(self) -> None:
        self.greeting = "Hello GenLayer from FactOracle"
        self.count    = 0
        self.active   = True

    @gl.public.write
    def increment(self) -> int:
        self.count += 1
        return self.count

    @gl.public.write
    def set_greeting(self, new_greeting: str) -> None:
        self.greeting = new_greeting

    @gl.public.view
    def get_greeting(self) -> str:
        return self.greeting

    @gl.public.view
    def get_count(self) -> int:
        return self.count

    @gl.public.view
    def get_active(self) -> bool:
        return self.active
