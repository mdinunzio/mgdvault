# API reference

## Functional API

::: mgdvault.api
    options:
      members:
        - get
        - set
        - delete
        - exists
        - list_keys
        - get_json
        - set_json
        - update
        - default_vault
        - set_default_vault
        - reset_default_vault
        - vault_from_env

## `.env` loading

::: mgdvault.envfile

## Vault interface

::: mgdvault.base.Vault

## Backends

::: mgdvault.backends.keepass.KeePassVault

::: mgdvault.backends.keyring.KeyringVault

::: mgdvault.backends.env.EnvVault

::: mgdvault.backends.memory.MemoryVault

## Keys

::: mgdvault.keys

## Settings

::: mgdvault.settings

## Exceptions

::: mgdvault.exceptions
