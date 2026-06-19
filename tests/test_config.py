from pathlib import Path

from itabashi.models import Config


def test_config_loads_values_from_dotenv(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    monkeypatch.delenv("LASTFM_USER", raising=False)
    monkeypatch.delenv("GENIUS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("POLL_SECONDS", raising=False)
    monkeypatch.delenv("OUTPUT_MODE", raising=False)

    Path(".env").write_text(
        "\n".join(
            [
                "LASTFM_API_KEY=lastfm-key",
                "LASTFM_USER=lastfm-user",
                "GENIUS_ACCESS_TOKEN='genius-token'",
                "POLL_SECONDS=45",
                "OUTPUT_MODE=png",
            ]
        ),
        encoding="utf-8",
    )

    config = Config.from_env()

    assert config.lastfm_api_key == "lastfm-key"
    assert config.lastfm_user == "lastfm-user"
    assert config.genius_access_token == "genius-token"
    assert config.poll_seconds == 45
    assert config.output_mode == "png"


def test_environment_values_override_dotenv(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LASTFM_API_KEY", "env-key")
    monkeypatch.setenv("LASTFM_USER", "env-user")
    monkeypatch.setenv("GENIUS_ACCESS_TOKEN", "env-token")

    Path(".env").write_text(
        "\n".join(
            [
                "LASTFM_API_KEY=dotenv-key",
                "LASTFM_USER=dotenv-user",
                "GENIUS_ACCESS_TOKEN=dotenv-token",
            ]
        ),
        encoding="utf-8",
    )

    config = Config.from_env()

    assert config.lastfm_api_key == "env-key"
    assert config.lastfm_user == "env-user"
    assert config.genius_access_token == "env-token"


def test_config_accepts_debug_output_mode(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LASTFM_API_KEY", "env-key")
    monkeypatch.setenv("LASTFM_USER", "env-user")
    monkeypatch.setenv("GENIUS_ACCESS_TOKEN", "env-token")
    monkeypatch.setenv("OUTPUT_MODE", "debug")

    config = Config.from_env()

    assert config.output_mode == "debug"
