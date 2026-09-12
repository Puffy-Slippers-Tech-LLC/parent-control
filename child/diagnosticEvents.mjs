// Pure validation shared by production GJS and Node privacy regressions.
export function diagnosticEnvelope(catalog, event, fields = {}) {
    if (typeof event !== 'string' || !Object.hasOwn(catalog, event))
        throw new Error('Unknown diagnostic event');
    const definition = catalog[event];
    if (!definition.components.includes('child') || definition.domain !== 'child')
        throw new Error('Invalid diagnostic source');
    if (fields === null || Object.getPrototypeOf(fields) !== Object.prototype ||
        Object.keys(fields).length !== Object.keys(definition.fields).length)
        throw new Error('Invalid diagnostic fields');
    const safe = {};
    for (const [key, spec] of Object.entries(definition.fields)) {
        if (!Object.hasOwn(fields, key))
            throw new Error('Missing diagnostic field');
        const value = fields[key];
        if (spec.type === 'bool' && typeof value === 'boolean')
            safe[key] = value;
        else if (spec.type === 'int' && Number.isSafeInteger(value) &&
            value >= spec.min && value <= spec.max)
            safe[key] = value;
        else
            throw new Error('Invalid diagnostic field');
    }
    return JSON.stringify({v: 1, event, operation: 0, fields: safe});
}
