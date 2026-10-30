import {defineConfig, globalIgnores} from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
    ...nextVitals,
    ...nextTs,
    // override eslint-config-next's default ignores
    globalIgnores([
        // its defaults:
        ".next/**",
        "out/**",
        "build/**",
        "next-env.d.ts",
        // local build output:
        ".vercel/**",
    ]),
]);

export default eslintConfig;
