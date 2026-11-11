"""Risk model files are loaded only when their signature matches, so a swapped file never runs."""
import os
import pickle
import sys

import pytest

AI_ML = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'ai-ml'))
if AI_ML not in sys.path:
    sys.path.append(AI_ML)

from predictions import model_store  # noqa: E402


class _Marker:
    """Unpickling this writes a file: proof that code ran."""
    def __init__(self, path):
        self.path = path

    def __reduce__(self):
        return (open, (self.path, 'w'))


def test_a_saved_model_loads_back(tmp_path, settings):
    settings.SECRET_KEY = 'unit-test-key'
    path = str(tmp_path / 'm.pkl')
    model_store.save_signed({'weights': [1, 2, 3]}, path)
    assert model_store.is_trusted(path) and model_store.load_signed(path) == {'weights': [1, 2, 3]}


def test_a_changed_file_is_refused_and_nothing_runs(tmp_path, settings):
    settings.SECRET_KEY = 'unit-test-key'
    path = str(tmp_path / 'm.pkl')
    model_store.save_signed({'ok': True}, path)
    marker = tmp_path / 'ran.txt'
    with open(path, 'wb') as f:
        f.write(pickle.dumps(_Marker(str(marker))))                  # someone drops their own file in
    assert not model_store.is_trusted(path)
    with pytest.raises(model_store.ModelFileNotTrusted):
        model_store.load_signed(path)
    assert not marker.exists()


def test_a_file_with_no_signature_is_refused(tmp_path, settings):
    settings.SECRET_KEY = 'unit-test-key'
    path = str(tmp_path / 'old.pkl')
    with open(path, 'wb') as f:
        pickle.dump({'old': 1}, f)
    assert not model_store.is_trusted(path)
    with pytest.raises(model_store.ModelFileNotTrusted):
        model_store.load_signed(path)


def test_a_different_key_does_not_trust_the_file(tmp_path, settings):
    settings.SECRET_KEY = 'key-one'
    path = str(tmp_path / 'm.pkl')
    model_store.save_signed({'ok': True}, path)
    settings.SECRET_KEY = 'key-two'
    assert not model_store.is_trusted(path)
