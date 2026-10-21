import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const html = readFileSync(new URL('../dist/hotel/browser/index.html', import.meta.url), 'utf8');
assert.doesNotMatch(
  html,
  /\bonload\s*=/i,
  'A strict CSP must not require an inline stylesheet load handler.',
);
assert.doesNotMatch(
  html,
  /<link[^>]+media=["']print["']/i,
  'The production stylesheet must apply on screen without JavaScript.',
);
assert.match(
  html,
  /<link[^>]+rel=["']stylesheet["'][^>]*>/i,
  'The production entry point must load its CSS.',
);
console.log('Production CSS passes strict CSP checks.');
