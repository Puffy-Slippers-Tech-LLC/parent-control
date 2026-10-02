"""Real gettext catalogues in private scratch; no GTK construction or installed app."""

import builtins
import gettext
import locale
import os
from pathlib import Path
import subprocess

import pytest

from common.oh_no_parent_control_ui.localization import DOMAIN, load_translations
from common.oh_no_parent_control_ui.languages import (
    SUPPORTED_LANGUAGES, language_direction, language_matches, supported_language,
)
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
        "pt": 'msgid "Hello"\nmsgstr "Olá, Portugal"\n',
        "zh_Hans": 'msgid "Hello"\nmsgstr "你好"\n',
        "zh_Hant": 'msgid "Hello"\nmsgstr "您好"\n',
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
    ("pt-PT", [], "Olá, Portugal"),
    ("", ["pt_PT.UTF-8"], "Olá, Portugal"),
    ("pt-BR", [], "Olá"),
    ("zh-Hant-TW", [], "您好"),
    ("", ["zh_TW.UTF-8"], "您好"),
    ("zh-Hans-TW", [], "你好"),
    ("de", ["fr_FR"], "Hello"),  # Supported choice, catalogue not shipped.
    ("zz-future", ["fr_FR"], "Hello"),
    ("", ["zz_ZZ", "fr_FR"], "Hello"),
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


def test_catalogue_choices_have_unique_ids_names_and_packaged_metadata(production_catalogues):
    import re
    ids = [language for language, _name in SUPPORTED_LANGUAGES]
    assert len(ids) == len(set(ids))
    assert ids[:10] == ['en', 'de', 'es', 'fr', 'pt-BR', 'zh-Hans', 'ru', 'it', 'pl', 'ja']
    for language, native_name in SUPPORTED_LANGUAGES:
        assert re.fullmatch(r'[a-z]{2,3}(?:-[A-Za-z]{2,4})?', language)
        assert native_name.strip() == native_name and native_name
        assert language_direction(language) in ('ltr', 'rtl')
        assert (ROOT / 'po' / (language.replace('-', '_') + '.po')).is_file()
        translations = load_translations(language, localedir=production_catalogues)
        assert isinstance(translations, gettext.GNUTranslations), language
        assert translations.info()['language'] == language.replace('-', '_')
        assert translations.gettext('Untranslated') == 'Untranslated'
        assert translations.gettext('Search languages') != 'Search languages' or language == 'en'
    assert {language for language in ids if language_direction(language) == 'rtl'} == {
        'ar', 'fa', 'he', 'ug', 'ur',
    }


@pytest.mark.parametrize('query,expected', [
    ('', {'pt', 'pt-BR', 'ru', 'sr-Latn'}),
    ('  gUÊS  ', {'pt', 'pt-BR'}),
    ('PORT*BR', {'pt-BR'}),
    ('РУСС', {'ru'}),
    ('sr-?atn', {'sr-Latn'}),
    ('[', set()),
    ('no such language', set()),
])
def test_language_search_matches_partial_native_names_and_ids(query, expected):
    choices = [('pt', 'Português'), ('pt-BR', 'Português (Brasil)'),
               ('ru', 'Русский'), ('sr-Latn', 'Srpski (latinica)')]
    assert {identity for identity, name in choices
            if language_matches(query, identity, name)} == expected


def test_locale_resolution_matches_shell_and_preserves_distinct_variants():
    import json
    vectors = [(language, language) for language, _name in SUPPORTED_LANGUAGES]
    vectors += [
        ('pt_PT.UTF-8', 'pt'), ('pt_BR.UTF-8', 'pt-BR'), ('pt-AO', 'pt'),
        ('zh_TW.UTF-8', 'zh-Hant'), ('zh_HK', 'zh-Hant'), ('zh-MO', 'zh-Hant'),
        ('zh_CN', 'zh-Hans'), ('zh-SG', 'zh-Hans'), ('zh', 'zh-Hans'),
        ('zh-Hans-TW', 'zh-Hans'), ('zh-Hant-CN', 'zh-Hant'),
        ('sr_RS.UTF-8@latin', 'sr-Latn'), ('sr@latin', 'sr-Latn'),
        ('sr-Latn-RS', 'sr-Latn'), ('sr-Cyrl-RS', 'sr'), ('sh', 'sr-Latn'),
        ('nb_NO', 'nb'), ('nn_NO', 'nn'), ('no_NO', 'nb'),
        ('iw_IL', 'he'), ('in_ID', 'id'), ('ar_EG', 'ar'), ('nl_NL', 'nl'),
        ('en_GB', 'en'), ('fr-CA', 'fr'), ('DE_de', 'de'),
        ('zz-future', 'en'), ('../../fr', 'en'), ('C.UTF-8', 'en'), ('', 'en'),
    ]
    for locale_name, expected in vectors:
        assert supported_language(locale_name) == expected, locale_name
    script = '''
import {readFileSync} from 'node:fs';
import {supportedLanguage} from './child/languages.mjs';
const languages = JSON.parse(readFileSync('common/oh_no_parent_control_ui/languages.json', 'utf8'));
const locales = JSON.parse(readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(locales.map(locale => supportedLanguage(locale, languages))));
'''
    result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                            input=json.dumps([locale for locale, _expected in vectors]),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [expected for _locale, expected in vectors]


def test_all_shipped_messages_preserve_operands_and_python_shell_plural_parity(production_catalogues):
    import ast
    import json
    import re
    # Use the POT rather than only the exported Shell dictionary: production
    # call sites also have contextual and inline messages outside that export.
    messages = []
    for block in (ROOT / 'po/oh-no-parent-control.pot').read_text(encoding='utf-8').split('\n\n'):
        fields, active = {}, None
        for line in block.splitlines():
            match = re.match(r'^(msgctxt|msgid|msgid_plural) (".*")$', line)
            if match:
                active = match[1]
                fields[active] = ast.literal_eval(match[2])
            elif line.startswith('"') and active:
                fields[active] += ast.literal_eval(line)
            elif not line.startswith('#'):
                active = None
        if fields.get('msgid'):
            messages.append((fields.get('msgctxt'), [fields['msgid']] +
                             ([fields['msgid_plural']] if 'msgid_plural' in fields else [])))
    placeholder = re.compile(r'%\(([^)]+)\)([sdg])')
    lookups, expected = [], []
    for language, _name in SUPPORTED_LANGUAGES:
        if language == 'en':
            continue
        translations = load_translations(language, localedir=production_catalogues)
        path = production_catalogues / language.replace('-', '_') / 'LC_MESSAGES' / (DOMAIN + '.mo')
        for context, forms in messages:
            key = (context, forms[0])
            # Cover every residue in the catalogue's integer plural rules,
            # including Arabic's six forms and Slavic teen/hundred boundaries.
            counts = (*range(201), 1000, 1000000) if len(forms) == 2 else (1,)
            indexes = set()
            for count in counts:
                # Missing entries must not silently pass via source fallback.
                source_key = context + '\x04' + forms[0] if context else forms[0]
                catalog_key = (source_key, translations.plural(count)) if len(forms) == 2 else source_key
                if len(forms) == 2:
                    indexes.add(translations.plural(count))
                assert translations._catalog.get(catalog_key), (language, key, count)
                translated = (translations.npgettext(context, *forms, count) if context and len(forms) == 2
                              else translations.pgettext(context, forms[0]) if context
                              else translations.ngettext(*forms, count) if len(forms) == 2
                              else translations.gettext(forms[0]))
                assert sorted(placeholder.findall(translated)) == sorted(placeholder.findall(forms[0])), (language, key)
                assert re.findall(r'</?[A-Za-z][^>]*>|&(?:[A-Za-z]+|#[0-9]+);', translated) == re.findall(
                    r'</?[A-Za-z][^>]*>|&(?:[A-Za-z]+|#[0-9]+);', forms[0]), (language, key, 'markup')
                if 'Oh No! Parent Control' in forms[0]:
                    assert 'Oh No! Parent Control' in translated, (language, key, 'branding')
                values = {name: 'Zoë <&>' if kind == 's' else count
                          for name, kind in placeholder.findall(forms[0])}
                assert isinstance(translated % values, str), (language, key)
                lookups.append([str(path), forms, count, context])
                expected.append(translated)
            if len(forms) == 2:
                nplurals = int(re.search(r'nplurals\s*=\s*(\d+)', translations.info()['plural-forms'])[1])
                assert indexes == set(range(nplurals)), (language, key, indexes)
    script = '''
import {readFileSync} from 'node:fs';
import {Catalogue} from './child/gettext.mjs';
const cache = new Map();
const results = JSON.parse(readFileSync(0, 'utf8')).map(([path, forms, n, context]) => {
    if (!cache.has(path)) cache.set(path, new Catalogue(readFileSync(path)));
    const catalogue = cache.get(path);
    return context && forms.length === 2 ? catalogue.npgettext(context, ...forms, n)
        : context ? catalogue.pgettext(context, forms[0])
        : forms.length === 2 ? catalogue.ngettext(...forms, n) : catalogue.gettext(forms[0]);
});
process.stdout.write(JSON.stringify(results));
'''
    result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                            input=json.dumps(lookups), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
    # Run the same real MO vectors in the product's JavaScript runtime too.
    vectors = production_catalogues / 'lookups.json'
    vectors.write_text(json.dumps(lookups), encoding='utf-8')
    gjs_script = production_catalogues / 'parity.mjs'
    gjs_script.write_text('''
import Gio from 'gi://Gio';
import {Catalogue} from %s;
const read = path => Gio.File.new_for_path(path).load_contents(null)[1];
const cache = new Map();
const results = JSON.parse(new TextDecoder().decode(read(ARGV[0]))).map(([path, forms, n, context]) => {
    if (!cache.has(path)) cache.set(path, new Catalogue(read(path)));
    const catalogue = cache.get(path);
    return context && forms.length === 2 ? catalogue.npgettext(context, ...forms, n)
        : context ? catalogue.pgettext(context, forms[0])
        : forms.length === 2 ? catalogue.ngettext(...forms, n) : catalogue.gettext(forms[0]);
});
print(JSON.stringify(results));
''' % json.dumps((ROOT / 'child/gettext.mjs').as_uri()), encoding='utf-8')
    result = subprocess.run(['gjs', '-m', str(gjs_script), str(vectors)], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected


@pytest.mark.parametrize('language,unit', [
    ('ru', 'часа'), ('pl', 'godziny'), ('en', 'hours'), ('de', 'Stunden'),
    ('es', 'horas'), ('it', 'ore'), ('ja', '時間'), ('zh-Hans', '小时'),
])
@pytest.mark.parametrize('count', [0.5, 1.5, 2.5, 5.5, 21.5])
def test_fractional_hours_use_native_wording(production_catalogues, language, unit, count):
    from common.oh_no_parent_control_ui.messages import hour_count
    assert hour_count(count).render(load_translations(language, localedir=production_catalogues)) == f'{count} {unit}'


@pytest.mark.parametrize('language,singular,plural', [('fr', 'heure', 'heures'), ('pt-BR', 'hora', 'horas')])
@pytest.mark.parametrize('count', [0.5, 1.5, 2.5, 5.5, 21.5])
def test_fractional_hours_below_two_retain_singular(
        production_catalogues, language, singular, plural, count):
    from common.oh_no_parent_control_ui.messages import hour_count
    translations = load_translations(language, localedir=production_catalogues)
    assert hour_count(count).render(translations) == f'{count} {singular if count < 2 else plural}'


def test_deferred_context_survives_named_formatting_and_english_fallback(catalogues):
    from common.oh_no_parent_control_ui.message import pgettext
    message = pgettext('verb', 'Open')
    assert message.render(load_translations('fr', localedir=catalogues)) == 'Ouvrir'
    formatted = pgettext('fractional hours below two', '%(count)g hours') % {'count': 1.5}
    assert formatted.context == 'fractional hours below two'
    assert formatted.render(gettext.NullTranslations()) == '1.5 hours'


@pytest.mark.parametrize('language,expected', [
    ('ru', ['0 часов', '1 час', '2 часа', '5 часов', '21 час']),
    ('pl', ['0 godzin', '1 godzina', '2 godziny', '5 godzin', '21 godzin']),
])
def test_integer_hours_retain_catalogue_plurals(production_catalogues, language, expected):
    from common.oh_no_parent_control_ui.messages import hour_count
    translations = load_translations(language, localedir=production_catalogues)
    assert [hour_count(count).render(translations) for count in (0, 1, 2, 5, 21)] == expected


@pytest.mark.parametrize('language,heading,categories', [
    ('de', 'Ein Fehler ist aufgetreten', 'Fehlerkategorien'),
    ('ru', 'Произошла ошибка', 'Категории ошибок'),
    ('pl', 'Wystąpił błąd', 'Kategorie błędów'),
])
def test_error_explanations_render_in_destination_language(
        production_catalogues, language, heading, categories):
    from common.oh_no_parent_control_ui.errors import ErrorReport
    from common.oh_no_parent_control_ui.message import render
    report = ErrorReport.capture('Parent App', RuntimeError('private-content'))
    text = render(report.message, load_translations(language, localedir=production_catalogues))
    assert text.startswith(heading + '\n')
    assert categories + ': RuntimeError' in text
    assert 'The operation could not be completed' not in text
    assert 'private-content' not in text


@pytest.mark.parametrize('language,units', [('fr', ('Ko', 'Mo')), ('ru', ('КБ', 'МБ'))])
def test_attachment_sizes_use_localized_units(production_catalogues, language, units):
    from common.oh_no_parent_control_ui.feedback import FeedbackDialog
    from common.oh_no_parent_control_ui.message import render
    translations = load_translations(language, localedir=production_catalogues)
    assert render(FeedbackDialog._format_size(1536), translations) == '1.5 ' + units[0]
    assert render(FeedbackDialog._format_size(1572864), translations) == '1.5 ' + units[1]
    assert render(FeedbackDialog._format_size(1023), translations) == translations.ngettext(
        '%(count)d byte', '%(count)d bytes', 1023) % {'count': 1023}
