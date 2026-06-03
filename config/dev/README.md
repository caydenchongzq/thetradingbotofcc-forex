# config/dev — development strategy configs

Standalone configs for backtesting strategies that are **not promoted to live**. Load one with:

    py scripts/run_backtest.py --config-file config/dev/<name>.yaml --walkforward

These never touch the ConfigStore HEAD, so live production is undisturbed. Copy
`example.yaml`, set `name:` to your registered strategy (see `--list-strategies`), tune its
params, and iterate. A strategy reaches live ONLY via a human-approved `ConfigStore.promote`.
