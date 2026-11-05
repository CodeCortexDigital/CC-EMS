"""Which AI provider the app uses, and that Gemini goes through Google's OpenAI-compatible endpoint under its own name."""
from services.ai.llm import GEMINI_BASE_URL, get_llm_client


def test_no_key_means_no_provider(settings):
    assert get_llm_client() is None


def test_gemini_is_used_when_only_its_key_is_set(settings):
    settings.GEMINI_API_KEY = 'test-key'
    client = get_llm_client()
    assert client is not None and client.provider == 'gemini'
    assert str(client.client.base_url).startswith(GEMINI_BASE_URL.rstrip('/'))
    assert client.model_for('fast') == settings.GEMINI_MODEL


def test_the_named_provider_wins_over_the_order_of_keys(settings):
    settings.OPENAI_API_KEY = 'openai-key'
    settings.GEMINI_API_KEY = 'gemini-key'
    assert get_llm_client().provider == 'openai'                    # first key found
    settings.AI_PROVIDER = 'gemini'
    assert get_llm_client().provider == 'gemini'


def test_a_named_provider_without_its_key_gives_no_client(settings):
    settings.AI_PROVIDER = 'gemini'
    assert get_llm_client() is None


def test_model_names_can_be_overridden(settings):
    settings.GEMINI_API_KEY = 'k'
    settings.AI_MODEL_FAST = 'gemini-fast-x'
    settings.AI_MODEL_SMART = 'gemini-smart-y'
    client = get_llm_client()
    assert (client.model_for('fast'), client.model_for('smart')) == ('gemini-fast-x', 'gemini-smart-y')


def test_openai_still_has_no_custom_endpoint(settings):
    settings.OPENAI_API_KEY = 'k'
    client = get_llm_client()
    assert client.provider == 'openai' and 'api.openai.com' in str(client.client.base_url)
