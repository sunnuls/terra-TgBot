import bcrypt

h = b"$2b$12$FQRZM1AQTr3JkL/EM/eqCubuGMHpwOItmX9LYsNWDQAYtD1KnzrKW"
print("admin123:", bcrypt.checkpw(b"admin123", h))
print("admin:", bcrypt.checkpw(b"admin", h))

# Generate new hash for admin123
new_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt(12))
print("new hash:", new_hash.decode())
