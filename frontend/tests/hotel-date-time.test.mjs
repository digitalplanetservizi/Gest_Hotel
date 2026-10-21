import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  formatHotelDateTime,
  hotelDateTimeInput,
  hotelDateTimeToIso,
} from '../src/app/core/hotel-date-time.ts';

test('extra dates use the hotel zone across midnight and daylight saving changes', () => {
  assert.equal(formatHotelDateTime('2026-10-24T22:30:00Z'), '25/10/2026 00:30');
  assert.equal(formatHotelDateTime('2026-10-25T02:30:00Z'), '25/10/2026 03:30');
  assert.equal(formatHotelDateTime('2026-10-24T22:30:00Z', 'America/New_York'), '24/10/2026 18:30');
  assert.equal(formatHotelDateTime(null), '—');
});

test('consumption inputs resolve using hotel timezone independently of browser timezone', () => {
  assert.equal(hotelDateTimeToIso('2026-10-24T18:45'), '2026-10-24T16:45:00.000Z');
  assert.equal(hotelDateTimeToIso('2026-11-24T18:45'), '2026-11-24T17:45:00.000Z');
  assert.equal(
    hotelDateTimeToIso('2026-10-24T18:45', 'America/New_York'),
    '2026-10-24T22:45:00.000Z',
  );
  assert.equal(hotelDateTimeInput('2026-10-24T16:45:00Z'), '2026-10-24T18:45');
});

test('nonexistent clock times and invalid consumption dates are rejected before submission', () => {
  assert.throws(() => hotelDateTimeToIso('2026-03-29T02:30'), /non è valida/);
  assert.throws(() => hotelDateTimeToIso('2026-02-30T10:00'), /non è valida/);
  assert.throws(() => hotelDateTimeToIso(''), /valida/);
});
