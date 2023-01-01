import * as fs from "fs";
import * as ts from "typescript";
import * as stringify from "json-stringify-safe";

const ignoredProperties = new Set([
    'pos', 'end', 'flags', 'modifierFlagsCache', 'transformFlags',
])

function replacer(key: string, val: any) {
    if (ignoredProperties.has(key)) {
        return undefined
    }
    if (key === 'kind') {
        return ts.SyntaxKind[val];
    } else {
        return val;
    }
}

function generateAstJson(
    fileNames: string[],
    options: ts.CompilerOptions,
) {
    const program = ts.createProgram(fileNames, options);
    for (const fileName of fileNames) {
        const source = program.getSourceFile(fileName);
        // We don't need the original source, but we'd like to have TypeScript version
        source.text = ts.version
        fs.writeFileSync(
            fileName.replace(".d.ts", ".json"),
            stringify(source, replacer, 4)
        );
    }
}

generateAstJson(process.argv.slice(2), {
    target: ts.ScriptTarget.Latest,
    experimentalDecorators: true,
    noResolve: true,
});