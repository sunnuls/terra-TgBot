import sys, importlib.util, typing_extensions, pydantic, pydantic_core

print("python:", sys.version)
for m in ("typing", "typing_extensions", "pydantic", "pydantic_core"):
    try:
        mod = __import__(m)
        spec = importlib.util.find_spec(m)
        print(f"{m:16} ->", (spec.origin if spec else "n/a"))
    except Exception as e:
        print(f"{m:16} !!", repr(e))
