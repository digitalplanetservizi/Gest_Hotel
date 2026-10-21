/** Calendar dates are independent from UTC offsets and daylight saving transitions. */
export function addCalendarDays(day: string, amount: number): string {
  const parsed = new Date(day + 'T12:00:00Z');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || !Number.isFinite(parsed.getTime()))
    throw new Error('Data non valida.');
  parsed.setUTCDate(parsed.getUTCDate() + amount);
  return parsed.toISOString().slice(0, 10);
}
export function inclusiveToExclusiveEnd(day: string): string {
  return addCalendarDays(day, 1);
}
export interface SegmentInterval {
  room: number;
  arrival: string;
  departure: string;
  active?: boolean;
}
export function segmentOverlapsDay(segment: SegmentInterval, room: number, day: string): boolean {
  return (
    segment.active !== false &&
    segment.room === room &&
    Date.parse(segment.arrival) < new Date(addCalendarDays(day, 1) + 'T00:00:00').getTime() &&
    Date.parse(segment.departure) > new Date(day + 'T00:00:00').getTime()
  );
}
