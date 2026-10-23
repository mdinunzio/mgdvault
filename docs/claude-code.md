# Claude Code skills

mgdvault ships two [Claude Code](https://claude.com/claude-code) skills so an
agent working in your projects knows how to handle secrets properly.

| Skill | Audience | What it teaches |
| --- | --- | --- |
| `mgdvault` | Any session that needs a credential | Check presence with `exists`/`list`, ask the user to run `mgdvault set KEY` themselves, read secrets at runtime with `mgdvault.get`, never print values into the conversation, troubleshooting |
| `mgdvault-integration` | Sessions adding mgdvault to a package | Key naming, lazy reads, auth/setup commands, JSON token bundles, `MemoryVault` in tests, migrating from keyring |

## Installing

Into the current project (`./.claude/skills/`):

```bash
uv run mgdvault install-skill
```

Globally (`~/.claude/skills/`), for every project, without needing a Python
project at all:

```bash
uv tool install mgdvault
mgdvault install-skill --global
```

Options: `--force` overwrites existing copies, `--skill NAME` installs one
skill. Restart Claude Code or run `/clear` so new skills load.

## Why the skills insist on not printing secrets

Conversation transcripts may be stored or synced off the machine. A value
that appears there has to be treated as leaked and rotated. The skills
therefore steer the agent to:

1. use `mgdvault exists` and `mgdvault list`, which show keys only;
2. have the human run `mgdvault set KEY` in their own terminal, where the
   hidden prompt keeps the value out of history and out of the transcript;
3. write code that calls `mgdvault.get()` at runtime rather than copying
   values into `.env` files or source.
