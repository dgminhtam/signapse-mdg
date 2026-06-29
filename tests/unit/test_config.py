from app.core.config import Settings


def test_twelvedata_effective_api_keys_accepts_one_key_from_plural_setting() -> None:
    settings = Settings(twelvedata_api_keys=" key-a ")

    assert settings.twelvedata_effective_api_keys() == ("key-a",)


def test_twelvedata_effective_api_keys_dedupes_and_skips_empty_values() -> None:
    settings = Settings(twelvedata_api_keys="key-a, key-b, key-a,, key-c ")

    assert settings.twelvedata_effective_api_keys() == ("key-a", "key-b", "key-c")


def test_singular_twelvedata_key_is_not_a_settings_field() -> None:
    assert "twelvedata_" + "api_key" not in Settings.model_fields
