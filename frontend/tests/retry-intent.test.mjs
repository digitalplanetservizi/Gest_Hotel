import { test } from 'node:test';
import assert from 'node:assert/strict';
import { RetryIntent } from '../src/app/core/retry-intent.ts';
test('a failed response can be retried without creating a second payment', () => {
  let sequence = 0;
  const intent = new RetryIntent(() => `key-${++sequence}`);
  const first = intent.forPayload({ stay: 1, amount: '50', method: 'cash' });
  assert.equal(intent.forPayload({ stay: 1, amount: '50', method: 'cash' }), first);
  assert.equal(sequence, 1);
});
test('a changed target or amount represents a new payment intent', () => {
  let sequence = 0;
  const intent = new RetryIntent(() => `key-${++sequence}`);
  const first = intent.forPayload({ stay: 1, amount: '50' });
  assert.notEqual(intent.forPayload({ stay: 1, amount: '25' }), first);
  assert.equal(sequence, 2);
});
test('after confirmed success the same amount can be paid again intentionally', () => {
  let sequence = 0;
  const intent = new RetryIntent(() => `key-${++sequence}`);
  const first = intent.forPayload({ stay: 1, amount: '50' });
  intent.succeeded();
  assert.notEqual(intent.forPayload({ stay: 1, amount: '50' }), first);
});
