const AUTOMATION_ID = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;


/** Publish stable Shell control metadata through AT-SPI. */
export function describeControl(actor, automationId, label, description) {
    if (typeof label !== 'string' || !label ||
        typeof description !== 'string' || !description)
        throw new Error('Shell controls require an accessible label and description');

    setAutomationId(actor, automationId);
    const accessible = actor.get_accessible();
    actor.accessible_name = label;
    accessible.set_description(description);
    return actor;
}


/** Publish a stable ID for a non-interactive Shell surface. */
export function setAutomationId(actor, automationId) {
    if (typeof automationId !== 'string' || !AUTOMATION_ID.test(automationId))
        throw new Error('automationId must be a lowercase hyphenated identifier');

    const accessible = actor.get_accessible();
    if (!accessible?.set_accessible_id)
        throw new Error('Shell accessibility provider cannot publish automation IDs');
    accessible.set_accessible_id(automationId);
    return actor;
}
