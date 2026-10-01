"""Real gettext catalogues in private scratch; no GTK, bus or installed app."""

import builtins
import gettext
import locale
import os
from pathlib import Path
import subprocess

import pytest

from common.oh_no_parent_control_ui.localization import DOMAIN, load_translations
from tests.support.paths import ROOT


def make_catalogues(root, *arguments):
    return subprocess.run(
        ["make", "--no-print-directory", "-f", str(ROOT / "Makefile"), *arguments],
        cwd=root, capture_output=True, text=True, timeout=30,
    )


@pytest.fixture
def catalogues(tmp_path):
    po = tmp_path / "po"
    po.mkdir()
    header = (ROOT / "po/en.po").read_text(encoding="utf-8")
    entries = {
        "fr": '''
msgid "Hello"
msgstr "Bonjour"

msgctxt "verb"
msgid "Open"
msgstr "Ouvrir"

msgctxt "adjective"
msgid "Open"
msgstr "Ouvert"

#, python-format
msgid "Hello, %(name)s"
msgstr "Bonjour, %(name)s"

#, fuzzy
msgid "Draft"
msgstr "Brouillon"
''',
        "ru": '''
msgid "minute"
msgid_plural "minutes"
msgstr[0] "минута"
msgstr[1] "минуты"
msgstr[2] "минут"

msgctxt "remaining"
msgid "minute"
msgid_plural "minutes"
msgstr[0] "осталась минута"
msgstr[1] "остались минуты"
msgstr[2] "осталось минут"
''',
        "pt_BR": 'msgid "Hello"\nmsgstr "Olá"\n',
        "zh_Hans": 'msgid "Hello"\nmsgstr "你好"\n',
    }
    for language, messages in entries.items():
        metadata = header.replace('Language: en', f'Language: {language}')
        if language == "ru":
            metadata = metadata.replace(
                'nplurals=2; plural=(n != 1);',
                'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : '
                'n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);',
            )
        (po / f"{language}.po").write_text(metadata + "\n" + messages, encoding="utf-8")
    result = make_catalogues(tmp_path, "translations", "LOCALE_OUTPUT=locale")
    assert result.returncode == 0, result.stdout + result.stderr
    return tmp_path / "locale"


@pytest.mark.parametrize("saved,session,expected", [
    ("fr-CA", ["de_DE"], "Bonjour"),
    ("", ["fr_CA.UTF-8", "C"], "Bonjour"),
    ("pt-PT", [], "Olá"),
    ("", ["pt_PT.UTF-8"], "Olá"),
    ("zh-Hant-TW", [], "你好"),
    ("", ["zh_TW.UTF-8"], "你好"),
    ("de", ["fr_FR"], "Hello"),  # Supported choice, catalogue not shipped.
    ("zz-future", ["fr_FR"], "Hello"),
    ("", ["nl_NL", "fr_FR"], "Hello"),
    ("../../fr", [], "Hello"),
    ("", [], "Hello"),
])
def test_selection_and_fallback(catalogues, saved, session, expected):
    translations = load_translations(saved, iter(session), localedir=catalogues)
    assert translations.gettext("Hello") == expected
    assert translations.gettext("Untranslated") == "Untranslated"


def test_context_unicode_and_named_formatting(catalogues):
    translations = load_translations("fr", localedir=catalogues)
    assert translations.pgettext("verb", "Open") == "Ouvrir"
    assert translations.pgettext("adjective", "Open") == "Ouvert"
    assert translations.pgettext("unknown", "Open") == "Open"
    assert translations.gettext("Hello, %(name)s") % {"name": "Zoë"} == "Bonjour, Zoë"
    assert translations.gettext("Draft") == "Draft"  # Fuzzy entries never ship.


def test_language_specific_plural_rules(catalogues):
    translations = load_translations("ru", localedir=catalogues)
    for number, expected, contextual in (
        (0, "минут", "осталось минут"),
        (1, "минута", "осталась минута"),
        (2, "минуты", "остались минуты"),
        (5, "минут", "осталось минут"),
        (11, "минут", "осталось минут"),
        (21, "минута", "осталась минута"),
    ):
        assert translations.ngettext("minute", "minutes", number) == expected
        assert translations.npgettext("remaining", "minute", "minutes", number) == contextual


def test_missing_catalogue_provides_all_standard_methods(tmp_path):
    translations = load_translations("fr", localedir=tmp_path)
    assert isinstance(translations, gettext.NullTranslations)
    assert translations.gettext("Hello") == "Hello"
    assert translations.pgettext("verb", "Open") == "Open"
    for number in (0, 1, 2):
        expected = "minute" if number == 1 else "minutes"
        assert translations.ngettext("minute", "minutes", number) == expected
        assert translations.npgettext("remaining", "minute", "minutes", number) == expected


def test_user_objects_do_not_share_language_or_change_process_state(catalogues, monkeypatch):
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.setenv(name, "fr_FR.UTF-8")
    before_environment = dict(os.environ)
    before_locale = locale.setlocale(locale.LC_ALL)
    sentinel = object()
    monkeypatch.setattr(builtins, "_", sentinel, raising=False)
    french = load_translations("fr", localedir=catalogues)
    portuguese = load_translations("pt-BR", localedir=catalogues)
    for _ in range(3):
        assert french.gettext("Hello") == "Bonjour"
        assert portuguese.gettext("Hello") == "Olá"
        assert load_translations(localedir=catalogues).gettext("Hello") == "Hello"
    assert builtins._ is sentinel
    assert dict(os.environ) == before_environment
    assert locale.setlocale(locale.LC_ALL) == before_locale


def test_corrupt_catalogue_is_reported(tmp_path):
    catalogue = tmp_path / "fr/LC_MESSAGES" / f"{DOMAIN}.mo"
    catalogue.parent.mkdir(parents=True)
    catalogue.write_bytes(b"not a gettext catalogue")
    with pytest.raises(OSError):
        load_translations("fr", localedir=tmp_path)


def test_build_refuses_broken_format_without_replacing_catalogue(catalogues):
    root = catalogues.parent
    source = root / "po/fr.po"
    source.write_text(source.read_text().replace('Bonjour, %(name)s', 'Bonjour, %(other)s'))
    target = catalogues / "fr/LC_MESSAGES" / f"{DOMAIN}.mo"
    before = target.read_bytes()
    result = make_catalogues(root, "-B", "translations", "LOCALE_OUTPUT=locale")
    assert result.returncode != 0
    assert "format" in result.stderr
    assert target.read_bytes() == before
    assert not Path(str(target) + ".tmp").exists()


def test_extraction_includes_marked_python_and_javascript_only(tmp_path):
    (tmp_path / "messages.py").write_text('''
# Translators: A button action.
_("Continue")
pgettext("verb", "Open")
ngettext("%(count)d minute", "%(count)d minutes", count)
npgettext("remaining", "minute", "minutes", count)
logger.info("Unlocalized diagnostic")
''')
    (tmp_path / "messages.mjs").write_text('''
_("Request time");
ngettext("One request", "Many requests", count);
console.log("Another diagnostic");
''')
    result = make_catalogues(
        tmp_path, "update-pot", "I18N_PYTHON_SOURCES=messages.py",
        "I18N_JS_SOURCES=messages.mjs", "POTFILE=messages.pot",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    template = (tmp_path / "messages.pot").read_text()
    for fragment in ('msgid "Continue"', 'msgid "Request time"', 'msgctxt "verb"',
                     'msgctxt "remaining"', 'msgid_plural "%(count)d minutes"',
                     'msgid_plural "Many requests"', '#. Translators: A button action.',
                     '#, python-format'):
        assert fragment in template
    assert "diagnostic" not in template


def test_production_extraction_and_catalogue_checks(tmp_path):
    result = make_catalogues(ROOT, "update-pot", f"POTFILE={tmp_path / 'product.pot'}")
    assert result.returncode == 0, result.stdout + result.stderr
    result = make_catalogues(ROOT, "check-translations")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope='module')
def production_catalogues(tmp_path_factory):
    destination = tmp_path_factory.mktemp('localization-review')
    result = make_catalogues(ROOT, 'translations', f'LOCALE_OUTPUT={destination}')
    assert result.returncode == 0, result.stdout + result.stderr
    return destination


def test_all_shipped_messages_preserve_operands_and_python_shell_plural_parity(production_catalogues):
    import json
    import re
    from tools.export_messages import export
    messages = export(ROOT / 'common/oh_no_parent_control_ui/messages.py')
    placeholder = re.compile(r'%\(([^)]+)\)([sdg])')
    lookups, expected = [], []
    for language in ('de', 'es', 'fr', 'pt-BR', 'zh-Hans', 'ru', 'it', 'pl', 'ja'):
        translations = load_translations(language, localedir=production_catalogues)
        path = production_catalogues / language.replace('-', '_') / 'LC_MESSAGES' / (DOMAIN + '.mo')
        for key, source in messages.items():
            forms = source if isinstance(source, list) else [source]
            counts = (0, 1, 2, 5, 11, 21, 22, 25, 101) if len(forms) == 2 else (1,)
            for count in counts:
                # Missing entries must not silently pass via source fallback.
                catalog_key = (forms[0], translations.plural(count)) if len(forms) == 2 else forms[0]
                assert translations._catalog.get(catalog_key), (language, key, count)
                translated = (translations.ngettext(*forms, count) if len(forms) == 2
                              else translations.gettext(forms[0]))
                assert sorted(placeholder.findall(translated)) == sorted(placeholder.findall(forms[0])), (language, key)
                values = {name: 'Zoë <&>' if kind == 's' else count
                          for name, kind in placeholder.findall(forms[0])}
                assert isinstance(translated % values, str), (language, key)
                lookups.append([str(path), forms, count])
                expected.append(translated)
    script = '''
import {readFileSync} from 'node:fs';
import {Catalogue} from './child/gettext.mjs';
const cache = new Map();
const results = JSON.parse(readFileSync(0, 'utf8')).map(([path, forms, n]) => {
    if (!cache.has(path)) cache.set(path, new Catalogue(readFileSync(path)));
    const catalogue = cache.get(path);
    return forms.length === 2 ? catalogue.ngettext(...forms, n) : catalogue.gettext(forms[0]);
});
process.stdout.write(JSON.stringify(results));
'''
    result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                            input=json.dumps(lookups), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected


@pytest.mark.parametrize('language,expected', [('ru', '1.5 часа'), ('pl', '1.5 godziny')])
def test_fractional_hours_use_native_wording(production_catalogues, language, expected):
    from common.oh_no_parent_control_ui.messages import hour_count
    assert hour_count(1.5).render(load_translations(language, localedir=production_catalogues)) == expected
