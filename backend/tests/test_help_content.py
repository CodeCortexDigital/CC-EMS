"""The starter help articles: well-formed, findable by the people they are for, and not promising what the app does not do."""
from django.core.management import call_command

from services.core.support import help_content
from services.core.support.models import HelpArticle
from tests.test_support import H, _client, sup  # noqa: F401  (sup is a fixture)

ROLES = {'admin', 'teacher', 'staff', 'parent', 'student'}
MODULES = {key for key, _ in HelpArticle.MODULES}


def test_every_article_is_well_formed():
    slugs = [a['slug'] for a in help_content.ARTICLES]
    assert len(slugs) == len(set(slugs)), 'duplicate slug'
    for a in help_content.ARTICLES:
        assert a['module'] in MODULES, a['slug']
        assert set(a.get('roles', [])) <= ROLES, a['slug']
        assert a['title'].strip() and a['body'].strip(), a['slug']
        assert len(a.get('summary', '')) <= 300 and len(a['title']) <= 200, a['slug']


def test_nothing_is_promised_that_the_app_does_not_do():
    text = ' '.join(a['body'] + a.get('summary', '') for a in help_content.ARTICLES).lower()
    for claim in ('jazzcash', 'easypaisa', 'live tracking', 'auto-send', 'sends it for you'):
        assert claim not in text, claim
    # AI help always says it is a draft and that it is not sent for you.
    ai = next(a for a in help_content.ARTICLES if a['slug'] == 'ai-drafts')['body'].lower()
    assert 'draft' in ai and 'never decides' in ai and 'until you' in ai


def test_the_new_articles_are_found_by_the_right_people_and_not_the_wrong_ones(sup):
    call_command('load_help_articles')
    admin, teacher, parent = _client(sup['admin']), _client(sup['teacher']), _client(sup['parent'])

    def slugs(client, q=''):
        return {a['slug'] for a in client.get(f'{H}/help/', {'q': q}).json()['articles']}

    assert {'daily-briefs', 'planning-reports', 'absence-steps', 'ai-settings', 'forms-permission-slips'} <= slugs(admin)
    assert 'daily-briefs' not in slugs(teacher) and 'daily-briefs' not in slugs(parent)       # administrators only, like the page
    assert {'interventions', 'safety-reports', 'ai-drafts', 'translate-and-summarise'} <= slugs(teacher)
    assert 'ai-settings' not in slugs(teacher)
    assert 'sign-forms' in slugs(parent) and 'translate-and-summarise' in slugs(parent)
    assert 'safety-reports' not in slugs(parent) and 'ai-drafts' not in slugs(parent)
    assert 'daily-briefs' in slugs(admin, 'morning brief')                                      # and it can be searched for


def test_the_new_topics_are_listed(sup):
    call_command('load_help_articles')
    topics = {m['key'] for m in _client(sup['admin']).get(f'{H}/help/').json()['modules']}
    assert {'reports', 'support', 'ai'} <= topics


def test_loading_again_adds_nothing_and_never_overwrites_an_edited_article(sup):
    call_command('load_help_articles')
    HelpArticle.objects.filter(slug='daily-briefs').update(title='Our own title')
    before = HelpArticle.objects.count()
    call_command('load_help_articles')
    assert HelpArticle.objects.count() == before
    assert HelpArticle.objects.get(slug='daily-briefs').title == 'Our own title'
