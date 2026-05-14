# { "Depends": "py-genlayer:test" }
# Minimal test contract — deploy this first to verify basic API works

from genlayer import *

class TestMinimal(gl.Contract):
    owner: str
    count: int
    data:  dict

    def __init__(self) -> None:
        self.owner = gl.message.sender_address
        self.count = 0
        self.data  = {}

    @gl.public.write
    def increment(self) -> int:
        self.count += 1
        return self.count

    @gl.public.view
    def get_count(self) -> int:
        return self.count

    @gl.public.view
    def get_owner(self) -> str:
        return self.owner
