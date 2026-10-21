import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  addCalendarDays,
  inclusiveToExclusiveEnd,
  segmentOverlapsDay,
} from '../src/app/core/date-range.ts';
test('API end is exclusive while the selected last day remains included', () => {
  assert.equal(inclusiveToExclusiveEnd('2026-10-19'), '2026-10-20');
  assert.equal(inclusiveToExclusiveEnd('2026-12-31'), '2027-01-01');
});
test('calendar arithmetic crosses daylight saving and leap days without UTC shifts', () => {
  assert.equal(addCalendarDays('2026-03-29', 1), '2026-03-30');
  assert.equal(addCalendarDays('2026-10-25', 1), '2026-10-26');
  assert.equal(addCalendarDays('2028-02-28', 1), '2028-02-29');
});
test('inactive and transferred segments never occupy a future room', () => {
  const segment = { room: 2, arrival: '2026-10-19T12:00:00', departure: '2026-10-21T10:00:00' };
  assert.equal(segmentOverlapsDay(segment, 2, '2026-10-20'), true);
  assert.equal(segmentOverlapsDay({ ...segment, active: false }, 2, '2026-10-20'), false);
  assert.equal(segmentOverlapsDay(segment, 3, '2026-10-20'), false);
  assert.equal(segmentOverlapsDay(segment, 2, '2026-10-21'), true);
  assert.equal(segmentOverlapsDay(segment, 2, '2026-10-22'), false);
});
test('half-open intervals allow checkout at midnight followed by another guest', () => {
  assert.equal(
    segmentOverlapsDay(
      { room: 2, arrival: '2026-10-19T12:00:00', departure: '2026-10-20T00:00:00' },
      2,
      '2026-10-20',
    ),
    false,
  );
});
