import {readFileSync} from 'node:fs';
import vm from 'node:vm';

// Host-only adapter for the production indicator class. Each call creates a
// fresh VM context; its platform dependencies are explicit test inputs. Real
// Shell lifecycle and input behavior remain covered by the nested-Shell suite.
export function createIndicator(dependencies = {}) {
    const source = readFileSync(
        new URL('../../../child/remainingTimeIndicator.js', import.meta.url), 'utf8')
        .replace(/^import[\s\S]*?;\n/gm, '')
        .replace('export const RemainingTimeIndicator', 'globalThis.RemainingTimeIndicator');
    const context = vm.createContext({
        GObject: {registerClass: klass => klass},
        PanelMenu: {Button: class {}},
        ...dependencies,
    });
    vm.runInContext(source, context, {filename: 'remainingTimeIndicator.js'});
    return new context.RemainingTimeIndicator();
}
