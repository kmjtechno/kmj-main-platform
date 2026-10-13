import { readFileSync } from 'node:fs';

/**
 * Reads a source file for text assertions while ignoring only LAYOUT.
 *
 * The source-assertion tests guard product-truth properties (permissions come
 * from the server, revocation needs confirmation, nothing invents a
 * measurement...). Matching raw text ties them to where the formatter happens
 * to wrap a line, so a formatting-only change turns them red. Runs of
 * whitespace therefore become one space, and the formatter's wrapping
 * artefacts around brackets and trailing commas are removed:
 * `foo(\n  bar,\n)` and `foo(bar)` compare equal.
 *
 * Identifiers, strings, operators and JSX text are untouched, so removing or
 * changing a guarded property still fails its assertion.
 */
export function readSourceText(path) {
    return readFileSync(path, 'utf8')
        .replace(/\s+/g, ' ')
        .replace(/([({[]) /g, '$1')
        .replace(/,? ([)}\]])/g, '$1');
}
