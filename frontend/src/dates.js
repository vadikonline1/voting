// Dates of the vote are days in the time zone of the APC. The server sends stored times as UTC, sometimes
// without the "Z" suffix, so a value without a zone is read as UTC.
export const APC_TIME_ZONE = "Europe/Chisinau";

function parseUtc(value) {
  if (!value) return null;
  const hasZone = /([zZ]|[+-]\d\d:?\d\d)$/.test(value);
  const date = new Date(hasZone ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** "2026-10-31" for an <input type="date">, in Chisinau time. */
export function dayInputValue(value) {
  const date = parseUtc(value);
  if (!date) return "";
  return new Intl.DateTimeFormat("en-CA", { timeZone: APC_TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}

/** "31.10.2026", in Chisinau time. */
export function formatDay(value) {
  const date = parseUtc(value);
  if (!date) return "—";
  return date.toLocaleDateString("ro-RO", { timeZone: APC_TIME_ZONE, day: "2-digit", month: "2-digit", year: "numeric" });
}
