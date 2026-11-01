// Solo da formato a lo que calculó la API: no cambia la zona ni vuelve a calcular nada.
const FECHA_HORA = new Intl.DateTimeFormat("es-CO", {
  timeZone: "America/Bogota",
  dateStyle: "medium",
  timeStyle: "short",
});
const UN_DECIMAL = new Intl.NumberFormat("es-CO", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const DOS_DECIMALES = new Intl.NumberFormat("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function fechaHora(iso: string): string {
  return FECHA_HORA.format(new Date(iso));
}

export function horas(valor: number): string {
  return `${UN_DECIMAL.format(valor)} h`;
}

export function confianza(valor: number): string {
  return DOS_DECIMALES.format(valor);
}
