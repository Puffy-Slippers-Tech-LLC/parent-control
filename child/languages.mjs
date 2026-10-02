/** Resolve only trusted catalogue IDs; mirrored by the shared Python resolver. */
export function supportedLanguage(localeName, languages) {
    const [locale, modifier = ''] = localeName.split('@');
    const normalized = locale.split('.')[0].replaceAll('_', '-').toLowerCase();
    const exact = languages.find(language => language.id.toLowerCase() === normalized);
    if (exact && !(normalized === 'sr' && modifier.toLowerCase() === 'latin'))
        return exact.id;
    const parts = normalized.split('-');
    const base = ({no: 'nb', iw: 'he', in: 'id', sh: 'sr'})[parts[0]] || parts[0];
    if (base === 'zh') {
        if (parts.includes('hans')) return 'zh-Hans';
        if (parts.includes('hant') || ['tw', 'hk', 'mo'].some(region => parts.includes(region)))
            return 'zh-Hant';
        return 'zh-Hans';
    }
    if (base === 'pt') return parts.includes('br') ? 'pt-BR' : 'pt';
    if (base === 'sr')
        return parts.includes('latn') || modifier.toLowerCase() === 'latin' || parts[0] === 'sh'
            ? 'sr-Latn' : 'sr';
    return languages.find(language => language.id === base)?.id ||
        languages.find(language => language.id.split('-')[0] === base)?.id || 'en';
}
