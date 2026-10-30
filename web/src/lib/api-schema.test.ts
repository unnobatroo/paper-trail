import {readFileSync} from "node:fs";
import openapiTS, {astToString, COMMENT_HEADER} from "openapi-typescript";
import {expect, test} from "vitest";

// api-schema.ts is generated, a stale copy = the ui drifting from the api again
test("generated api types match openapi.json", async () => {
    const spec = new URL("../../openapi.json", import.meta.url);
    const generated = COMMENT_HEADER + astToString(await openapiTS(spec));
    const onDisk = readFileSync(new URL("./api-schema.ts", import.meta.url), "utf8");
    expect(onDisk, "run `npm run gen:api`").toBe(generated);
});
