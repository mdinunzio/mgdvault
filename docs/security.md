# Security notes

## What mgdvault protects against

- **Secrets in source and `.env` files.** Code reads from the vault at
  runtime; the only configuration value is the master password, which is a
  single thing to protect instead of one per service.
- **Secrets on the command line.** The CLI never accepts values as arguments.
- **Plaintext at rest.** The KeePass backend encrypts with AES-256 under an
  Argon2-derived key; the file and its directory are created owner-only.
- **Concurrent corruption.** Writes are serialised with a file lock and
  re-read the file first. `update(key, fn)` extends that lock across a
  read-modify-write, which is what OAuth refresh needs; `get` then `set` is
  a race and should not be used for rotating tokens.

## What it does not protect against

- **Anyone who has both the `.kdbx` file and the password.** Keep
  `MGDVAULT_PASSWORD` out of version control and out of transcripts.
- **Code running as you.** Any process in your session that can read the
  environment variable can read the vault. This is the same trust level as a
  `.env` file, with encryption at rest added.
- **The derived key in process memory.** For speed, the unlocked database and
  derived key stay in memory for the life of the process. Call
  `vault.close()` to drop them.

## Practical advice

- Use a long passphrase; Argon2 slows brute force but does not make a weak
  password strong.
- Prefer exporting `MGDVAULT_PASSWORD` from a shell profile or a secrets
  manager over putting it in per-project `.env` files, so there is one copy.
- If a value ever appears in a chat transcript, log, or screenshot, rotate it.
- `MGDVAULT_PATH` makes per-project vaults easy; committing the encrypted file
  is acceptable, committing the password is not.
- The database is a normal KeePass file: open it in KeePassXC to audit what is
  stored.
