const formatters = new Map<string, Intl.DateTimeFormat>();

function parts(iso: string, timeZone: string): Record<string, string> {
  let formatter = formatters.get(timeZone);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat('en-GB', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    });
    formatters.set(timeZone, formatter);
  }
  return Object.fromEntries(formatter.formatToParts(new Date(iso)).map((p) => [p.type, p.value]));
}

export function hotelDateTimeInput(iso: string, timeZone = 'Europe/Rome'): string {
  const p = parts(iso, timeZone);
  return `${p['year']}-${p['month']}-${p['day']}T${p['hour']}:${p['minute']}`;
}

export function formatHotelDateTime(iso: string | null, timeZone = 'Europe/Rome'): string {
  if (!iso) return '—';
  const p = parts(iso, timeZone);
  return `${p['day']}/${p['month']}/${p['year']} ${p['hour']}:${p['minute']}`;
}

/** Resolve a wall-clock input in the hotel's zone, independently of the browser zone. */
export function hotelDateTimeToIso(value: string, timeZone = 'Europe/Rome'): string {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
    throw new Error('Inserisci una data e ora di consumazione valida.');
  }
  const wallClock = Date.parse(value + ':00Z');
  if (!Number.isFinite(wallClock)) {
    throw new Error('Inserisci una data e ora di consumazione valida.');
  }
  let timestamp = wallClock;
  for (let attempt = 0; attempt < 4; attempt++) {
    const formatted = hotelDateTimeInput(new Date(timestamp).toISOString(), timeZone);
    if (formatted === value) return new Date(timestamp).toISOString();
    timestamp += wallClock - Date.parse(formatted + ':00Z');
  }
  throw new Error('La data e ora di consumazione non è valida nel fuso della struttura.');
}
