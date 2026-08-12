import tsParser from "@typescript-eslint/parser";

// Config exclusiva para eslint_complexity_analyzer.py (MC-05 en JS/TS).
// Solo habilita la regla "complexity" con umbral 0 para que ESLint
// reporte la complejidad ciclomática de TODAS las funciones del
// workspace analizado (no solo las que exceden un umbral): el umbral
// de aceptabilidad real (<=10) lo aplica Python en el analizador, igual
// que radon_analyzer.py.
export default [
  {
    files: ["**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx"],
    languageOptions: {
      parser: tsParser,
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: { complexity: ["error", 0] },
  },
];
