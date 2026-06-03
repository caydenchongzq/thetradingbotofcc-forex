"""Env-driven config loader (spec 00 §6 / 07)."""

from pathlib import Path

from src.common.config import load_config, read_env_file


def test_loads_defaults_from_yaml():
    cfg = load_config(env={}, config_file="config/default.yaml")
    assert cfg.config_version == 1
    assert cfg.schema_version == 3
    assert cfg.risk.base_risk_fraction == 0.0035
    assert cfg.risk.killswitch.halt_pct == 0.60
    assert cfg.account.initial == 100_000
    assert cfg.strategy["instrument"] == "EURUSD"


def test_env_overrides_account_and_state_dir():
    cfg = load_config(
        env={"TBOT_ACCOUNT_INITIAL": "50000", "TBOT_STATE_DIR": "/tmp/state",
             "TBOT_ENV": "demo"},
        config_file="config/default.yaml",
    )
    assert cfg.account.initial == 50_000
    # Compare as Path so the assertion is OS-agnostic (Windows renders separators
    # as backslashes); the loader stores exactly what the env var provided.
    assert cfg.state_dir == Path("/tmp/state")
    assert cfg.env == "demo"


def test_env_file_reader_and_mt5_config(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# comment\n"
        "TBOT_MT5_LOGIN=520123\n"
        'TBOT_MT5_PASSWORD="s3cret"\n'
        "TBOT_MT5_SERVER=FTMO-Demo2\n"
        "BLANK_IGNORED\n",
        encoding="utf-8",
    )
    parsed = read_env_file(env_path)
    assert parsed["TBOT_MT5_LOGIN"] == "520123"
    assert parsed["TBOT_MT5_PASSWORD"] == "s3cret"   # quotes stripped
    assert "BLANK_IGNORED" not in parsed              # no '=' -> ignored

    cfg = load_config(env=parsed, config_file="config/default.yaml")
    assert cfg.mt5.login == 520123
    assert cfg.mt5.server == "FTMO-Demo2"
    assert cfg.mt5.configured is True
    assert cfg.execution.magic == 770042
    assert cfg.execution.symbol == "EURUSD"


def test_mt5_unconfigured_by_default():
    cfg = load_config(env={}, config_file="config/default.yaml")
    assert cfg.mt5.configured is False


def test_env_file_strips_inline_comments_but_keeps_hash_in_values(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "TBOT_ACCOUNT_INITIAL=100000       # initial balance; sets the floors\n"
        "TBOT_STATE_DIR=./state            # where state lives\n"
        "TBOT_MT5_PASSWORD=pa#ss\n"               # no space before # -> kept
        'TBOT_MT5_SERVER="FTMO#Demo"\n',          # quoted -> # kept
        encoding="utf-8",
    )
    parsed = read_env_file(env_path)
    assert parsed["TBOT_ACCOUNT_INITIAL"] == "100000"   # inline comment stripped
    assert parsed["TBOT_STATE_DIR"] == "./state"
    assert parsed["TBOT_MT5_PASSWORD"] == "pa#ss"        # hash preserved (no space)
    assert parsed["TBOT_MT5_SERVER"] == "FTMO#Demo"      # hash preserved (quoted)

    # And the float conversion that previously crashed now succeeds.
    cfg = load_config(env=parsed, config_file="config/default.yaml")
    assert cfg.account.initial == 100_000


def test_alerts_resolved_from_env():
    cfg = load_config(env={"TBOT_TELEGRAM_BOT_TOKEN": "123:abc",
                           "TBOT_TELEGRAM_CHAT_ID": "999",
                           "TBOT_HEALTHCHECKS_URL": "https://hc.io/abc"},
                      config_file="config/default.yaml")
    assert cfg.alerts.telegram_configured is True
    assert cfg.alerts.telegram_bot_token == "123:abc"
    assert cfg.alerts.healthchecks_url == "https://hc.io/abc"


def test_alerts_unconfigured_by_default():
    cfg = load_config(env={}, config_file="config/default.yaml")
    assert cfg.alerts.telegram_configured is False
    assert cfg.alerts.healthchecks_url is None
