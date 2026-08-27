"""
Tests for credential redaction in serialised configuration

`GET /api/status` and `PUT /api/config` both hand the caller the whole config
object. It holds `omi_api_key` - the upstream api.omi.me credential - so without
redaction possession of the shared API key yields a second, unrelated credential
over plain HTTP.

The redaction is derived from the field name, so these tests pin the convention
rather than one field: a secret added to SystemConfig later must be redacted
without anyone editing this file or main.py.
"""
import dataclasses
from unittest.mock import AsyncMock

import pytest

from utils import auth
from utils.config import (
    CONFIGURED_SUFFIX,
    SECRET_FIELD_SUFFIXES,
    SystemConfig,
    is_secret_field_name,
    redact_secrets,
    secret_field,
)

SECRET_VALUE = "omi-upstream-credential-do-not-leak"


@pytest.fixture
def config_with_secret():
    """A SystemConfig whose upstream credential is set to a known value"""
    config = SystemConfig()
    config.omi_api_key = SECRET_VALUE
    return config


@pytest.fixture
def system(main_module, monkeypatch):
    """An OmiCompanionSystem holding a known upstream credential.

    `create_app()` keeps its system instance to itself, so the object is built
    here directly to get at the config the routes serialise.
    """
    monkeypatch.delenv(auth.API_KEY_ENV_VAR, raising=False)
    system = main_module.OmiCompanionSystem()
    system.config.omi_api_key = SECRET_VALUE
    # The stubbed client returns a bare mock, which does not survive JSON
    # encoding; /api/status awaits this on every call.
    system.ollama_client.health_check = AsyncMock(return_value=True)
    return system


@pytest.fixture
def app(system):
    """Overrides the conftest fixture so `client` talks to *this* system"""
    return system.app


class TestSecretDetection:
    """Which fields count as secrets"""

    @pytest.mark.parametrize(
        "name",
        ["omi_api_key", "api_key", "refresh_token", "client_secret", "db_password"],
    )
    def test_convention_suffixes_are_secret(self, name):
        assert is_secret_field_name(name) is True

    @pytest.mark.parametrize(
        "name", ["ollama_url", "api_port", "log_level", "keyring", "passwordless"]
    )
    def test_ordinary_names_are_not_secret(self, name):
        assert is_secret_field_name(name) is False

    def test_every_documented_suffix_is_honoured(self):
        for suffix in SECRET_FIELD_SUFFIXES:
            assert is_secret_field_name(f"some{suffix}") is True

    def test_the_known_credential_is_detected(self):
        assert "omi_api_key" in SystemConfig().secret_field_names()

    def test_ordinary_fields_are_not_detected(self):
        names = SystemConfig().secret_field_names()
        assert "ollama_url" not in names
        assert "api_port" not in names

    def test_explicit_marker_catches_an_off_convention_name(self):
        """A secret whose name breaks the convention can still opt in"""

        @dataclasses.dataclass
        class WithMarker(SystemConfig):
            upstream_credential: str = secret_field("hunter2")

        names = WithMarker().secret_field_names()
        assert "upstream_credential" in names
        assert "omi_api_key" in names


class TestRedactSecrets:
    """The redaction itself"""

    def test_secret_is_replaced_by_a_boolean(self):
        result = redact_secrets({"omi_api_key": SECRET_VALUE}, {"omi_api_key"})
        assert result == {f"omi_api_key{CONFIGURED_SUFFIX}": True}

    def test_unset_secret_reports_not_configured(self):
        result = redact_secrets({"omi_api_key": ""}, {"omi_api_key"})
        assert result == {f"omi_api_key{CONFIGURED_SUFFIX}": False}

    def test_whitespace_only_secret_reports_not_configured(self):
        result = redact_secrets({"omi_api_key": "   "}, {"omi_api_key"})
        assert result[f"omi_api_key{CONFIGURED_SUFFIX}"] is False

    def test_non_secret_values_pass_through_untouched(self):
        values = {"api_port": 8000, "ollama_url": "http://localhost:11434"}
        assert redact_secrets(values, {"omi_api_key"}) == values


class TestToPublicDict:
    """SystemConfig.to_public_dict()"""

    def test_secret_value_is_absent(self, config_with_secret):
        public = config_with_secret.to_public_dict()
        assert "omi_api_key" not in public
        assert SECRET_VALUE not in str(public)

    def test_indicator_reports_configured(self, config_with_secret):
        assert config_with_secret.to_public_dict()["omi_api_key_configured"] is True

    def test_indicator_reports_not_configured(self):
        config = SystemConfig()
        config.omi_api_key = ""
        assert config.to_public_dict()["omi_api_key_configured"] is False

    def test_ordinary_settings_survive(self, config_with_secret):
        public = config_with_secret.to_public_dict()
        assert public["api_port"] == config_with_secret.api_port
        assert public["ollama_url"] == config_with_secret.ollama_url

    def test_no_field_matching_the_convention_is_serialised(self, config_with_secret):
        """The property that has to hold for a secret added later"""
        leaked = [key for key in config_with_secret.to_public_dict() if is_secret_field_name(key)]
        assert leaked == []

    def test_to_dict_still_carries_the_secret(self, config_with_secret):
        """The unredacted view stays available for in-process callers"""
        assert config_with_secret.to_dict()["omi_api_key"] == SECRET_VALUE


class TestEndpointsDoNotLeak:
    """The routes that serialise config"""

    def test_status_redacts_the_credential(self, client, api_key):
        response = client.get(
            "/api/status", headers={auth.API_KEY_HEADER_NAME: api_key}
        )
        assert response.status_code == 200
        config = response.json()["config"]
        assert "omi_api_key" not in config
        assert config["omi_api_key_configured"] is True
        assert SECRET_VALUE not in response.text

    def test_config_update_response_redacts_the_credential(self, client, api_key):
        response = client.put(
            "/api/config",
            json={"video_fps": 30},
            headers={auth.API_KEY_HEADER_NAME: api_key},
        )
        assert response.status_code == 200
        config = response.json()["config"]
        assert config["video_fps"] == 30
        assert "omi_api_key" not in config
        assert config["omi_api_key_configured"] is True
        assert SECRET_VALUE not in response.text

    def test_config_broadcast_redacts_the_credential(self, client, api_key):
        """The same payload goes out over /ws/live to every listener"""
        with client.websocket_connect(
            "/ws/live", headers={auth.API_KEY_HEADER_NAME: api_key}
        ) as websocket:
            assert websocket.receive_json()["type"] == "status"
            client.put(
                "/api/config",
                json={"video_fps": 30},
                headers={auth.API_KEY_HEADER_NAME: api_key},
            )
            message = websocket.receive_json()

        assert message["type"] == "config_updated"
        assert "omi_api_key" not in message["data"]
        assert message["data"]["omi_api_key_configured"] is True
