// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ['dist/*'],
  },
  {
    // Quotes in React Native <Text> need no escaping; that rule is for HTML.
    rules: { 'react/no-unescaped-entities': 'off' },
  },
]);
