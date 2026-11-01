import { ETIQUETAS_SEMAFORO, type Semaforo as ValorSemaforo } from "./tipos";

// El color lo decide la API (contexto.md 4.7); aquí se muestra con su nombre, no solo el color.
export function Semaforo({ valor }: { valor: ValorSemaforo }) {
  return <span className={`semaforo semaforo-${valor.toLowerCase()}`}>{ETIQUETAS_SEMAFORO[valor]}</span>;
}
