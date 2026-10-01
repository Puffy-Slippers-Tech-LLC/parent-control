// Private GNU MO reader. No process locale changes and no executable expressions.
export function pluralFunction(expression, forms) {
    const tokens = expression.match(/\d+|n|&&|\|\||==|!=|<=|>=|[()?:!<>+*/%\-]/g) ?? [];
    if (tokens.length > 256 || tokens.join('') !== expression.replace(/\s/g, ''))
        throw new Error('Invalid plural expression');
    let position = 0;
    const precedence = {'||': 1, '&&': 2, '==': 3, '!=': 3, '<': 4, '>': 4,
        '<=': 4, '>=': 4, '+': 5, '-': 5, '*': 6, '/': 6, '%': 6};
    const operations = {
        '||': (a, b) => Number(Boolean(a() || b())),
        '&&': (a, b) => Number(Boolean(a() && b())),
        '==': (a, b) => Number(a() === b()), '!=': (a, b) => Number(a() !== b()),
        '<': (a, b) => Number(a() < b()), '>': (a, b) => Number(a() > b()),
        '<=': (a, b) => Number(a() <= b()), '>=': (a, b) => Number(a() >= b()),
        '+': (a, b) => a() + b(), '-': (a, b) => a() - b(),
        '*': (a, b) => a() * b(), '/': (a, b) => Math.trunc(a() / b()),
        '%': (a, b) => a() % b(),
    };
    function parse(minimum = 0) {
        const token = tokens[position++];
        let left;
        if (token === 'n') left = n => n;
        else if (/^\d+$/.test(token ?? '')) left = () => Number(token);
        else if (token === '!' || token === '-' || token === '+') {
            const operand = parse(7);
            left = n => token === '!' ? Number(!operand(n))
                : token === '-' ? -operand(n) : operand(n);
        } else if (token === '(') {
            left = parse();
            if (tokens[position++] !== ')') throw new Error('Invalid plural grouping');
        } else throw new Error('Invalid plural operand');
        while (position < tokens.length) {
            const operator = tokens[position];
            const level = precedence[operator];
            if (level === undefined || level < minimum) break;
            position++;
            const previous = left;
            const right = parse(level + 1);
            left = n => operations[operator](() => previous(n), () => right(n));
        }
        if (minimum === 0 && tokens[position] === '?') {
            position++;
            const condition = left;
            const yes = parse();
            if (tokens[position++] !== ':') throw new Error('Invalid plural conditional');
            const no = parse();
            left = n => condition(n) ? yes(n) : no(n);
        }
        return left;
    }
    const evaluate = parse();
    if (position !== tokens.length || !Number.isInteger(forms) || forms < 1 || forms > 6)
        throw new Error('Invalid plural metadata');
    return n => {
        if (!Number.isSafeInteger(n) || n < 0) throw new Error('Invalid plural count');
        const index = evaluate(n);
        if (!Number.isInteger(index) || index < 0 || index >= forms)
            throw new Error('Invalid plural result');
        return index;
    };
}

export class Catalogue {
    constructor(bytes = null) {
        this.messages = new Map();
        this.plural = n => Number(n !== 1);
        if (bytes === null) return;
        if (bytes.length < 28 || bytes.length > 16 * 1024 * 1024)
            throw new Error('Invalid catalogue size');
        const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
        const little = view.getUint32(0, true) === 0x950412de;
        if (!little && view.getUint32(0, false) !== 0x950412de)
            throw new Error('Invalid catalogue magic');
        const word = offset => view.getUint32(offset, little);
        if (word(4) !== 0) throw new Error('Unsupported catalogue revision');
        const count = word(8), originals = word(12), translations = word(16);
        if (count > 65536 || originals + count * 8 > bytes.length ||
            translations + count * 8 > bytes.length)
            throw new Error('Invalid catalogue tables');
        const decoder = new TextDecoder('utf-8', {fatal: true});
        const read = offset => {
            const length = word(offset), start = word(offset + 4);
            if (start + length >= bytes.length || bytes[start + length] !== 0)
                throw new Error('Invalid catalogue string');
            return decoder.decode(bytes.subarray(start, start + length));
        };
        for (let i = 0; i < count; i++) {
            const source = read(originals + i * 8);
            const text = read(translations + i * 8);
            this.messages.set(source.split('\0')[0], text.split('\0'));
        }
        const header = this.messages.get('')?.[0] ?? '';
        if (!/charset=UTF-8/i.test(header)) throw new Error('Unsupported catalogue encoding');
        const plural = header.match(/Plural-Forms:\s*nplurals=(\d+);\s*plural=([^\n]+);/i);
        if (!plural) throw new Error('Missing plural metadata');
        this.plural = pluralFunction(plural[2], Number(plural[1]));
    }

    gettext(source) { return this.messages.get(source)?.[0] || source; }
    pgettext(context, source) {
        return this.messages.get(`${context}\x04${source}`)?.[0] || source;
    }
    ngettext(singular, plural, count) {
        return this.messages.get(singular)?.[this.plural(count)] || (count === 1 ? singular : plural);
    }
    npgettext(context, singular, plural, count) {
        return this.messages.get(`${context}\x04${singular}`)?.[this.plural(count)] ||
            (count === 1 ? singular : plural);
    }
}
