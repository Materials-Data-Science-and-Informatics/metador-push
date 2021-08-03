module.exports = {
  extends: ['eslint:recommended'],
  parser: '@typescript-eslint/parser', // add the TypeScript parser
  parserOptions: {
    ecmaVersion: 2019,
    sourceType: 'module'
  },
  env: {
    es6: true,
    browser: true,
    node: true
  },
  plugins: [
    'svelte3',
    '@typescript-eslint' // add the TypeScript plugin
  ],
  ignorePatterns: [
    'public/build/'
  ],
  overrides: [ // this stays the same
    {
      files: ['*.svelte'],
      processor: 'svelte3/svelte3'
    }
  ],
  rules: {
    // ...
  },
  settings: {
    'svelte3/typescript': () => require('typescript'), // pass the TypeScript package to the Svelte plugin
  }
};
