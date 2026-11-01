import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode, type Ref } from "react";
import { registrarPqrs, type Fallo } from "./api";
import { confianza, fechaHora, horas } from "./formato";
import { Semaforo } from "./Semaforo";
import {
  CANALES,
  ETIQUETAS_CANAL,
  ETIQUETAS_ESTADO,
  ETIQUETAS_ESTADO_IA,
  ETIQUETAS_ORIGEN,
  ETIQUETAS_RIESGO,
  ETIQUETAS_TIPO,
  LIMITES,
  TIPOS_DOCUMENTO,
  type Canal,
  type ErrorCampo,
  type PqrsCreada,
  type PqrsNueva,
  type TipoDocumento,
} from "./tipos";

// La hora del campo se envía como hora de Colombia (UTC−05:00, sin horario de verano).
// Si la fecha no es válida o es posterior al registro, lo dice el 400 de la API.
const ZONA = "-05:00";

interface Formulario {
  canal: string;
  sede: string;
  fechaRadicacion: string;
  texto: string;
  pacienteMenorDeEdad: boolean;
  tipoDocumento: string;
  numeroDocumento: string;
  nombre: string;
  telefono: string;
  correo: string;
}

const VACIO: Formulario = {
  canal: "",
  sede: "",
  fechaRadicacion: "",
  texto: "",
  pacienteMenorDeEdad: false,
  tipoDocumento: "",
  numeroDocumento: "",
  nombre: "",
  telefono: "",
  correo: "",
};

// Nombre de cada campo del formulario en los errores de la API.
const CAMPOS_API: Record<keyof Formulario, string> = {
  canal: "canal",
  sede: "sede",
  fechaRadicacion: "fechaRadicacion",
  texto: "texto",
  pacienteMenorDeEdad: "pacienteMenorDeEdad",
  tipoDocumento: "peticionario.tipoDocumento",
  numeroDocumento: "peticionario.numeroDocumento",
  nombre: "peticionario.nombre",
  telefono: "peticionario.telefono",
  correo: "peticionario.correo",
};
const CAMPOS_DEL_FORMULARIO = new Set(Object.values(CAMPOS_API));

// Un campo vacío no se envía: si era obligatorio, la API responde «es obligatorio».
function valor(texto: string): string | undefined {
  return texto === "" ? undefined : texto;
}

function conZona(local: string): string {
  // datetime-local entrega AAAA-MM-DDTHH:mm, o con segundos si se escriben.
  return (local.length === 16 ? `${local}:00` : local) + ZONA;
}

function aPqrsNueva(formulario: Formulario): PqrsNueva {
  return {
    canal: valor(formulario.canal) as Canal | undefined,
    sede: valor(formulario.sede),
    fechaRadicacion: formulario.fechaRadicacion === "" ? undefined : conZona(formulario.fechaRadicacion),
    texto: valor(formulario.texto),
    pacienteMenorDeEdad: formulario.pacienteMenorDeEdad,
    peticionario: {
      tipoDocumento: valor(formulario.tipoDocumento) as TipoDocumento | undefined,
      numeroDocumento: valor(formulario.numeroDocumento),
      nombre: valor(formulario.nombre),
      telefono: valor(formulario.telefono),
      correo: valor(formulario.correo),
    },
  };
}

function agruparPorCampo(errores: ErrorCampo[]): Record<string, string[]> {
  const agrupados: Record<string, string[]> = {};
  for (const { campo, mensaje } of errores) (agrupados[campo] ??= []).push(mensaje);
  return agrupados;
}

export function Registro() {
  const base = useId();
  const [formulario, setFormulario] = useState<Formulario>(VACIO);
  const [enviando, setEnviando] = useState(false);
  const [creada, setCreada] = useState<PqrsCreada | null>(null);
  const [fallo, setFallo] = useState<Fallo | null>(null);
  const avisoRef = useRef<HTMLDivElement>(null);
  const resultadoRef = useRef<HTMLElement>(null);

  const porCampo = agruparPorCampo(fallo?.errores ?? []);
  const otrosErrores = (fallo?.errores ?? []).filter((e) => !CAMPOS_DEL_FORMULARIO.has(e.campo));

  useEffect(() => {
    if (fallo) avisoRef.current?.focus();
  }, [fallo]);

  useEffect(() => {
    if (creada) resultadoRef.current?.focus();
  }, [creada]);

  function cambiar<K extends keyof Formulario>(campo: K, nuevo: Formulario[K]) {
    setFormulario((actual) => ({ ...actual, [campo]: nuevo }));
  }

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setEnviando(true);
    setCreada(null);
    setFallo(null);
    const resultado = await registrarPqrs(aPqrsNueva(formulario));
    setEnviando(false);
    if (resultado.ok) {
      // Los datos del peticionario no se quedan en el formulario después del registro.
      setFormulario(VACIO);
      setCreada(resultado.datos);
    } else {
      setFallo(resultado.fallo);
    }
  }

  function limpiar() {
    setFormulario(VACIO);
    setFallo(null);
    setCreada(null);
  }

  // Etiqueta, control y mensajes de error de la API para un campo.
  function campo(
    nombre: keyof Formulario,
    etiqueta: string,
    limite: string | null,
    control: (props: PropsControl) => ReactNode,
    clase = "campo",
  ) {
    const id = `${base}-${nombre}`;
    const mensajes = porCampo[CAMPOS_API[nombre]] ?? [];
    const idError = `${id}-error`;
    return (
      <div className={clase}>
        <label htmlFor={id}>
          {etiqueta} {limite && <span className="limite">({limite})</span>}
        </label>
        {control({
          id,
          "aria-invalid": mensajes.length > 0 ? true : undefined,
          "aria-describedby": mensajes.length > 0 ? idError : undefined,
        })}
        {mensajes.length > 0 && (
          <p className="error-campo" id={idError}>
            {mensajes.join(" ")}
          </p>
        )}
      </div>
    );
  }

  return (
    <section className="seccion" aria-labelledby={`${base}-titulo`}>
      <h2 id={`${base}-titulo`}>Registrar PQRS</h2>
      <p className="ayuda">
        La API valida los datos, calcula el vencimiento y hace la clasificación provisional. Use solo datos
        sintéticos.
      </p>

      {creada && <ResultadoRegistro creada={creada} refSeccion={resultadoRef} />}

      {fallo && (
        <div className="aviso aviso-error" role="alert" tabIndex={-1} ref={avisoRef}>
          <h3>{fallo.titulo}</h3>
          {fallo.detalle && <p>{fallo.detalle}</p>}
          {otrosErrores.length > 0 && (
            <ul>
              {otrosErrores.map((e) => (
                <li key={`${e.campo}-${e.mensaje}`}>
                  {e.campo}: {e.mensaje}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <form className="tarjeta" onSubmit={enviar} noValidate autoComplete="off">
        <fieldset>
          <legend>PQRS</legend>
          <div className="rejilla">
            {campo("canal", "Canal", null, (props) => (
              <select {...props} value={formulario.canal} onChange={(e) => cambiar("canal", e.target.value)}>
                <option value="">Seleccione…</option>
                {CANALES.map((canal) => (
                  <option key={canal} value={canal}>
                    {ETIQUETAS_CANAL[canal]}
                  </option>
                ))}
              </select>
            ))}
            {campo("sede", "Sede", `opcional, máx. ${LIMITES.sede}`, (props) => (
              <input
                {...props}
                maxLength={LIMITES.sede}
                value={formulario.sede}
                onChange={(e) => cambiar("sede", e.target.value)}
              />
            ))}
            {campo("fechaRadicacion", "Fecha y hora de radicación", "hora de Colombia, UTC−05:00", (props) => (
              <input
                {...props}
                type="datetime-local"
                value={formulario.fechaRadicacion}
                onChange={(e) => cambiar("fechaRadicacion", e.target.value)}
              />
            ))}
            {campo(
              "pacienteMenorDeEdad",
              "Paciente menor de edad",
              null,
              (props) => (
                <input
                  {...props}
                  type="checkbox"
                  checked={formulario.pacienteMenorDeEdad}
                  onChange={(e) => cambiar("pacienteMenorDeEdad", e.target.checked)}
                />
              ),
              "campo casilla",
            )}
            {campo(
              "texto",
              "Texto",
              `de ${LIMITES.textoMinimo} a ${LIMITES.texto.toLocaleString("es-CO")} caracteres`,
              (props) => (
                <>
                  <textarea
                    {...props}
                    maxLength={LIMITES.texto}
                    value={formulario.texto}
                    onChange={(e) => cambiar("texto", e.target.value)}
                  />
                  <span className="contador" aria-live="polite">
                    {formulario.texto.length.toLocaleString("es-CO")} / {LIMITES.texto.toLocaleString("es-CO")}
                  </span>
                </>
              ),
              "campo campo-ancho",
            )}
          </div>
        </fieldset>

        <fieldset>
          <legend>Peticionario</legend>
          <p className="ayuda">La API cifra estos datos y no los devuelve; la interfaz no los guarda.</p>
          <div className="rejilla">
            {campo("tipoDocumento", "Tipo de documento", null, (props) => (
              <select {...props} value={formulario.tipoDocumento} onChange={(e) => cambiar("tipoDocumento", e.target.value)}>
                <option value="">Seleccione…</option>
                {TIPOS_DOCUMENTO.map((tipo) => (
                  <option key={tipo} value={tipo}>
                    {tipo}
                  </option>
                ))}
              </select>
            ))}
            {campo("numeroDocumento", "Número de documento", `máx. ${LIMITES.numeroDocumento}`, (props) => (
              <input
                {...props}
                autoComplete="off"
                maxLength={LIMITES.numeroDocumento}
                value={formulario.numeroDocumento}
                onChange={(e) => cambiar("numeroDocumento", e.target.value)}
              />
            ))}
            {campo("nombre", "Nombre", `máx. ${LIMITES.nombre}`, (props) => (
              <input
                {...props}
                autoComplete="off"
                maxLength={LIMITES.nombre}
                value={formulario.nombre}
                onChange={(e) => cambiar("nombre", e.target.value)}
              />
            ))}
            {campo("telefono", "Teléfono", `opcional, máx. ${LIMITES.telefono}`, (props) => (
              <input
                {...props}
                type="tel"
                autoComplete="off"
                maxLength={LIMITES.telefono}
                value={formulario.telefono}
                onChange={(e) => cambiar("telefono", e.target.value)}
              />
            ))}
            {campo("correo", "Correo", "opcional", (props) => (
              <input
                {...props}
                type="email"
                autoComplete="off"
                value={formulario.correo}
                onChange={(e) => cambiar("correo", e.target.value)}
              />
            ))}
          </div>
        </fieldset>

        <div className="acciones">
          <button type="submit" disabled={enviando}>
            {enviando ? "Registrando…" : "Registrar PQRS"}
          </button>
          <button type="button" className="secundario" onClick={limpiar} disabled={enviando}>
            Limpiar
          </button>
        </div>
      </form>
    </section>
  );
}

interface PropsControl {
  id: string;
  "aria-invalid": true | undefined;
  "aria-describedby": string | undefined;
}

function ResultadoRegistro({ creada, refSeccion }: { creada: PqrsCreada; refSeccion: Ref<HTMLElement> }) {
  const clasificacion = creada.clasificacionProvisional;
  const vencimiento = creada.vencimiento;
  return (
    <section className="tarjeta resultado" aria-label="PQRS registrada" tabIndex={-1} ref={refSeccion}>
      <h3>PQRS registrada</h3>
      <p className="radicado">{creada.radicado}</p>
      <p className="ayuda">
        Estado: {ETIQUETAS_ESTADO[creada.estado]} · Clasificación con IA: {ETIQUETAS_ESTADO_IA[creada.estadoIa]}. La
        IA trabaja en segundo plano; la bandeja muestra el estado actual.
      </p>
      <div className="datos">
        <div>
          <h3>Clasificación provisional</h3>
          {clasificacion ? (
            <dl>
              <dt>Origen</dt>
              <dd>{ETIQUETAS_ORIGEN[clasificacion.origen]}</dd>
              <dt>Tipo</dt>
              <dd>{ETIQUETAS_TIPO[clasificacion.tipo]}</dd>
              <dt>Nivel de riesgo</dt>
              <dd>{ETIQUETAS_RIESGO[clasificacion.nivelRiesgo]}</dd>
              <dt>Atributo</dt>
              <dd>{clasificacion.atributo?.nombre ?? "Sin atributo"}</dd>
              <dt>Área sugerida</dt>
              <dd>{clasificacion.area?.nombre ?? "Sin área"}</dd>
              <dt>Confianza</dt>
              <dd>{confianza(clasificacion.confianza)}</dd>
              <dt>Requiere revisión</dt>
              <dd>{clasificacion.requiereRevision ? "Sí" : "No"}</dd>
            </dl>
          ) : (
            <p>Sin clasificación provisional.</p>
          )}
        </div>
        <div>
          <h3>Vencimiento</h3>
          <dl>
            <dt>Semáforo</dt>
            <dd>
              <Semaforo valor={vencimiento.semaforo} />
            </dd>
            <dt>Vence</dt>
            <dd>{fechaHora(vencimiento.fecha)}</dd>
            <dt>Horas restantes</dt>
            <dd>{horas(vencimiento.horasRestantes)}</dd>
            <dt>Regla</dt>
            <dd>{vencimiento.regla}</dd>
          </dl>
        </div>
      </div>
    </section>
  );
}
