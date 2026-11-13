"""The off-site time stamp for the audit chain (RFC 3161): the request, the checks on the reply, the kept stamps and the check against them."""
from unittest import mock

import pytest

from services.core.audit import anchors, chain
from services.core.audit.models import AuditLog, ChainAnchor
from tests.safety_helpers import api, make_user, two_schools

T = '/api/v1/security/timestamps/'
URL = 'https://tsa.example/stamp'


@pytest.fixture
def world(db, settings):
    settings.TIMESTAMP_AUTHORITY_URL = URL
    a, b = two_schools()
    return {'a': a, 'b': b, 'admin': make_user(a, 'head@a.test', 'admin'), 'admin_b': make_user(b, 'head@b.test', 'admin'),
            'parent': make_user(a, 'mom@a.test', 'parent')}


def _record(world, n=1, school='a'):
    for i in range(n):
        chain.append(user=world['admin'], school=world[school], action='UPDATE', resource_type='ai.settings.test', new_data={'n': i})
    return str(world[school].pk)


def _reply(digest_hex, status=0):
    """A minimal answer shaped like a TimeStampResp: SEQUENCE { SEQUENCE { INTEGER status }, ...the digest }."""
    body = bytes([0x30, 0x03, 0x02, 0x01, status]) + b'\x04\x20' + bytes.fromhex(digest_hex) + b'\x00' * 20
    return b'\x30' + bytes([len(body)]) + body


def _tsa(status=0, digest=None):
    def post(url, request):
        return _reply(digest or request[-35:-3].hex(), status)
    return mock.patch('services.core.audit.anchors._post', side_effect=post)


class TestRequest:
    def test_it_is_a_sha256_time_stamp_request_that_asks_for_the_certificate(self):
        digest = 'ab' * 32
        req = anchors.build_request(digest)
        assert req[:2] == bytes([0x30, len(req) - 2]) and len(req) == 59
        assert req[2:5] == bytes.fromhex('020101') and bytes.fromhex(digest) in req and req.endswith(bytes.fromhex('0101ff'))
        assert bytes.fromhex('0609608648016503040201') in req                 # the SHA-256 identifier

    def test_only_a_32_byte_hash_is_accepted(self):
        with pytest.raises(anchors.AnchorError):
            anchors.build_request('ab' * 16)


class TestReply:
    D = 'cd' * 32

    def test_a_granted_reply_for_the_same_hash_passes(self):
        anchors.check_reply(_reply(self.D), self.D)
        anchors.check_reply(_reply(self.D, 1), self.D)                         # granted with modifications

    def test_a_refusal_a_reply_for_another_hash_and_rubbish_are_refused(self):
        with pytest.raises(anchors.AnchorError, match='refused'):
            anchors.check_reply(_reply(self.D, 2), self.D)
        with pytest.raises(anchors.AnchorError, match='different hash'):
            anchors.check_reply(_reply('ee' * 32), self.D)
        for rubbish in (b'', b'hello', b'\x30\x03\x02\x01\x00', b'\x31' + b'\x00' * 60, b'\x30\x80' + b'\x01' * 60):
            with pytest.raises(anchors.AnchorError):
                anchors.check_reply(rubbish, self.D)


class TestAnchor:
    def test_it_does_nothing_until_an_authority_is_set(self, world, settings):
        name = _record(world)
        settings.TIMESTAMP_AUTHORITY_URL = ''
        with pytest.raises(anchors.AnchorError, match='No time-stamping authority'):
            anchors.anchor(name)

    def test_nothing_to_stamp_in_an_empty_chain(self, world):
        with pytest.raises(anchors.AnchorError, match='no records'):
            anchors.anchor(str(world['a'].pk))

    def test_the_newest_hash_is_sent_and_the_reply_kept_and_nothing_else_leaves(self, world):
        name = _record(world, 3)
        with _tsa() as post:
            a = anchors.anchor(name)
        sent_url, sent = post.call_args.args
        head = chain.verify(name)['heads'][name]
        assert sent_url == URL and bytes.fromhex(head) in sent and len(sent) == 59      # a hash, nothing about the school or its people
        assert a.seq == 3 and a.head_hash == head and a.school_id == world['a'].pk and a.authority == URL and bytes(a.token)

    def test_it_is_not_repeated_when_nothing_new_was_written(self, world):
        name = _record(world)
        with _tsa() as post:
            first = anchors.anchor(name)
            again = anchors.anchor(name)
        assert first.pk == again.pk and post.call_count == 1 and ChainAnchor.objects.count() == 1
        _record(world)
        with _tsa():
            assert anchors.anchor(name).seq == 2
        assert ChainAnchor.objects.count() == 2

    def test_an_unreachable_or_refusing_authority_leaves_no_stamp(self, world):
        name = _record(world)
        with mock.patch('services.core.audit.anchors._post', side_effect=OSError('down')):
            with pytest.raises(anchors.AnchorError, match='could not be reached'):
                anchors.anchor(name)
        with _tsa(status=2):
            with pytest.raises(anchors.AnchorError, match='refused'):
                anchors.anchor(name)
        assert ChainAnchor.objects.count() == 0


class TestCheckAgainstStamps:
    def test_an_untouched_history_verifies(self, world):
        name = _record(world, 2)
        with _tsa():
            anchors.anchor(name)
        _record(world)
        assert anchors.check(name) == [] and chain.verify(name)['ok'] is True

    def test_history_rewritten_after_it_was_stamped_is_caught_even_if_the_chain_is_made_consistent(self, world):
        name = _record(world, 3)
        with _tsa():
            anchors.anchor(name)
        # the whole chain is rewritten with its head: it is consistent in itself, but no longer what the authority signed
        AuditLog._base_manager.filter(chain=name, seq=3).update(entry_hash='f' * 64)
        from services.core.audit.models import AuditChainHead
        AuditChainHead.objects.filter(chain=name).update(last_hash='f' * 64)
        out = chain.verify(name)
        assert any('time-stamped by an outside authority' in p for p in out['problems']) and out['ok'] is False

    def test_a_removed_record_is_caught(self, world):
        name = _record(world, 2)
        with _tsa():
            anchors.anchor(name)
        AuditLog._base_manager.filter(chain=name, seq=2).delete()
        assert anchors.check(name)

    def test_another_schools_stamp_is_not_checked_against_this_chain(self, world):
        a, b = _record(world, 1), _record(world, 2, 'b')
        with _tsa():
            anchors.anchor(b)
        assert anchors.check(a) == []


class TestScreen:
    def test_it_shows_the_state_and_the_stamps_kept(self, world):
        d = api(world['admin']).get(T).json()
        assert d['enabled'] is True and d['authority'] == URL and d['records'] == 0 and d['stamps'] == [] and d['up_to_date'] is False
        _record(world, 2)
        with _tsa():
            d = api(world['admin']).post(T).json()
        assert d['records'] == 2 and d['up_to_date'] is True and d['stamps'][0]['seq'] == 2 and d['chain']['ok'] is True
        assert AuditLog.objects.filter(resource_type='security/chain-timestamp', school=world['a']).exists()
        _record(world)
        assert api(world['admin']).get(T).json()['up_to_date'] is False

    def test_a_refusal_is_explained(self, world):
        _record(world)
        with mock.patch('services.core.audit.anchors._post', side_effect=OSError('down')):
            r = api(world['admin']).post(T)
        assert r.status_code == 400 and 'could not be reached' in r.json()['error']

    def test_it_says_when_no_authority_is_set(self, world, settings):
        settings.TIMESTAMP_AUTHORITY_URL = ''
        d = api(world['admin']).get(T).json()
        assert d['enabled'] is False
        assert api(world['admin']).post(T).status_code == 400

    def test_the_signed_reply_can_be_downloaded_for_checking(self, world):
        _record(world)
        with _tsa():
            d = api(world['admin']).post(T).json()
        r = api(world['admin']).get(f"{T}{d['stamps'][0]['id']}/")
        assert r.status_code == 200 and r['Content-Type'] == 'application/timestamp-reply' and r['X-Chain-Hash'] == d['stamps'][0]['hash']
        assert bytes.fromhex(d['stamps'][0]['hash']) in r.content

    def test_only_this_schools_administrator(self, world):
        _record(world)
        with _tsa():
            d = api(world['admin']).post(T).json()
        token = f"{T}{d['stamps'][0]['id']}/"
        assert api(world['parent']).get(T).status_code == 403 and api(world['parent']).post(T).status_code == 403
        assert api().get(T).status_code == 401
        assert api(world['admin_b']).get(token).status_code == 404
        assert api(world['admin_b']).get(T).json()['stamps'] == []
