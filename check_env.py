import sys, site, pprint
print("python exe:", sys.executable)
print("python ver:", sys.version)

print("\nsite-packages:", *site.getsitepackages(), sep="\n  - ")
print("\nsys.path (top 10):")
pprint.pp(sys.path[:10])

print("\n-- modules locations --")
import typing, typing_extensions, pydantic, pydantic_core
print("typing           =", typing.__file__)
print("typing_extensions=", typing_extensions.__file__)
print("pydantic         =", pydantic.__file__, pydantic.__version__)
print("pydantic_core    =", pydantic_core.__file__, pydantic_core.__version__)

from pydantic import BaseModel
class User(BaseModel):
    id: int
    name: str
print("\nPydantic OK:", User(id=1, name="ok"))

