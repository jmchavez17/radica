import { useEffect, useId, useState, type FormEvent } from "react";
import { listarPqrs, type Fallo, type FiltrosBandeja } from "./api";
import { fechaHora, horas } from "./formato";
import { Semaforo } from "./Semaforo";
import {
  ESTADOS_PQRS,
  ETIQUETAS_ESTADO,
  ETIQUETAS_RIESGO,
  ETIQUETAS_SEMAFORO,
  ETIQUETAS_TIPO,
  SEMAFOROS,
  TAMANOS_PAGINA,
  TAMANO_POR_DEFECTO,
  TIPOS_PQRS,
  type EstadoPqrs,
  type PaginaPqrs,
  type Semaforo as ValorSemaforo,
  type TipoPqrs,
} from "./tipos";

const SIN_FILTROS: FiltrosBandeja = { semaforo: "", estado: "", tipo: "", idArea: "" };

interface Consulta {
  filtros: FiltrosBandeja;
  pagina: number;
  tamano: number;
  // Cambia con «Actualizar» para repetir la misma consulta.
  vez: number;
}

export function Bandeja() {
  const base = useId();
  const [filtros, setFiltros] = useState<FiltrosBandeja>(SIN_FILTROS);
  const [tamano, setTamano] = useState<number>(TAMANO_POR_DEFECTO);
  const [consulta, setConsulta] = useState<Consulta>({
    filtros: SIN_FILTROS,
    pagina: 1,
    tamano: TAMANO_POR_DEFECTO,
    vez: 0,
  });
  const [pagina, setPagina] = useState<PaginaPqrs | null>(null);
  const [fallo, setFallo] = useState<Fallo | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let vigente = true;
    setCargando(true);
    listarPqrs(consulta.filtros, consulta.pagina, consulta.tamano).then((resultado) => {
      if (!vigente) return;
      setCargando(false);
      setPagina(resultado.ok ? resultado.datos : null);
      setFallo(resultado.ok ? null : resultado.fallo);
    });
    return () => {
      vigente = false;
    };
  }, [consulta]);

  function aplicar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setConsulta((actual) => ({ filtros, pagina: 1, tamano, vez: actual.vez + 1 }));
  }

  function irA(numero: number) {
    setConsulta((actual) => ({ ...actual, pagina: numero, vez: actual.vez + 1 }));
  }

  function cambiar<K extends keyof FiltrosBandeja>(nombre: K, valor: FiltrosBandeja[K]) {
    setFiltros((actual) => ({ ...actual, [nombre]: valor }));
  }

  const totalPaginas = pagina ? Math.max(1, Math.ceil(pagina.total / consulta.tamano)) : 1;
  const id = (nombre: string) => `${base}-${nombre}`;

  return (
    <section className="seccion" aria-labelledby={id("titulo")}>
      <h2 id={id("titulo")}>Bandeja</h2>
      <p className="ayuda">
        El semáforo, las horas restantes y el orden los calcula la API al consultar: primero las vencidas y luego
        por vencimiento.
      </p>

      <form className="tarjeta filtros" onSubmit={aplicar} noValidate aria-label="Filtros">
        <div className="campo">
          <label htmlFor={id("semaforo")}>Semáforo</label>
          <select
            id={id("semaforo")}
            value={filtros.semaforo}
            onChange={(e) => cambiar("semaforo", e.target.value as ValorSemaforo | "")}
          >
            <option value="">Todos</option>
            {SEMAFOROS.map((valor) => (
              <option key={valor} value={valor}>
                {ETIQUETAS_SEMAFORO[valor]}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label htmlFor={id("estado")}>Estado</label>
          <select
            id={id("estado")}
            value={filtros.estado}
            onChange={(e) => cambiar("estado", e.target.value as EstadoPqrs | "")}
          >
            <option value="">Todos</option>
            {ESTADOS_PQRS.map((valor) => (
              <option key={valor} value={valor}>
                {ETIQUETAS_ESTADO[valor]}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label htmlFor={id("tipo")}>Tipo</label>
          <select id={id("tipo")} value={filtros.tipo} onChange={(e) => cambiar("tipo", e.target.value as TipoPqrs | "")}>
            <option value="">Todos</option>
            {TIPOS_PQRS.map((valor) => (
              <option key={valor} value={valor}>
                {ETIQUETAS_TIPO[valor]}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label htmlFor={id("idArea")}>Área sugerida (id)</label>
          <input
            id={id("idArea")}
            type="number"
            inputMode="numeric"
            value={filtros.idArea}
            onChange={(e) => cambiar("idArea", e.target.value)}
          />
        </div>
        <div className="campo">
          <label htmlFor={id("tamano")}>Por página</label>
          <select id={id("tamano")} value={tamano} onChange={(e) => setTamano(Number(e.target.value))}>
            {TAMANOS_PAGINA.map((valor) => (
              <option key={valor} value={valor}>
                {valor}
              </option>
            ))}
          </select>
        </div>
        <div className="acciones">
          <button type="submit">Aplicar</button>
          <button
            type="button"
            className="secundario"
            onClick={() => setConsulta((actual) => ({ ...actual, vez: actual.vez + 1 }))}
          >
            Actualizar
          </button>
        </div>
      </form>

      <p className="vacio" aria-live="polite">
        {cargando ? "Cargando…" : ""}
      </p>

      {fallo && (
        <div className="aviso aviso-error" role="alert">
          <h3>{fallo.titulo}</h3>
          {fallo.detalle && <p>{fallo.detalle}</p>}
          {fallo.errores.length > 0 && (
            <ul>
              {fallo.errores.map((e) => (
                <li key={`${e.campo}-${e.mensaje}`}>
                  {e.campo}: {e.mensaje}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {pagina && (
        <div className="tarjeta">
          {pagina.elementos.length === 0 ? (
            <p className="vacio">No hay PQRS con estos filtros.</p>
          ) : (
            <div className="tabla-contenedor">
              <table>
                <caption>
                  {pagina.total} PQRS en total, en el orden en que las entrega la API.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Semáforo</th>
                    <th scope="col">Radicado</th>
                    <th scope="col">Tipo</th>
                    <th scope="col">Riesgo</th>
                    <th scope="col">Área sugerida</th>
                    <th scope="col">Estado</th>
                    <th scope="col">Vence</th>
                    <th scope="col">Horas restantes</th>
                    <th scope="col">Regla</th>
                  </tr>
                </thead>
                <tbody>
                  {pagina.elementos.map((pqrs) => (
                    <tr key={pqrs.id}>
                      <td>
                        <Semaforo valor={pqrs.vencimiento.semaforo} />
                      </td>
                      <th scope="row">{pqrs.radicado}</th>
                      <td>{ETIQUETAS_TIPO[pqrs.tipo]}</td>
                      <td>{ETIQUETAS_RIESGO[pqrs.nivelRiesgo]}</td>
                      <td>{pqrs.area ? `${pqrs.area.nombre} (${pqrs.area.id})` : "Sin área"}</td>
                      <td>{ETIQUETAS_ESTADO[pqrs.estado]}</td>
                      <td>{fechaHora(pqrs.vencimiento.fecha)}</td>
                      <td className="numero">{horas(pqrs.vencimiento.horasRestantes)}</td>
                      <td className="regla">{pqrs.vencimiento.regla}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <nav className="paginacion" aria-label="Paginación">
            <button
              type="button"
              className="secundario"
              disabled={cargando || pagina.pagina <= 1}
              onClick={() => irA(pagina.pagina - 1)}
            >
              Anterior
            </button>
            <span>
              Página {pagina.pagina} de {totalPaginas}
            </span>
            <button
              type="button"
              className="secundario"
              disabled={cargando || pagina.pagina >= totalPaginas}
              onClick={() => irA(pagina.pagina + 1)}
            >
              Siguiente
            </button>
          </nav>
        </div>
      )}
    </section>
  );
}
