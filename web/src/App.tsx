import { useEffect, useState } from "react";
import { Bandeja } from "./Bandeja";
import { Registro } from "./Registro";

type Vista = "registro" | "bandeja";

function vistaDeLaUrl(): Vista {
  return window.location.hash === "#bandeja" ? "bandeja" : "registro";
}

export function App() {
  const [vista, setVista] = useState<Vista>(vistaDeLaUrl);

  useEffect(() => {
    const alCambiar = () => setVista(vistaDeLaUrl());
    window.addEventListener("hashchange", alCambiar);
    return () => window.removeEventListener("hashchange", alCambiar);
  }, []);

  return (
    <>
      <header className="encabezado">
        <div className="marca">
          <h1>Radica</h1>
          <span className="sintetico">Datos sintéticos</span>
        </div>
        <nav aria-label="Secciones">
          <a href="#registro" aria-current={vista === "registro" ? "page" : undefined}>
            Registrar PQRS
          </a>
          <a href="#bandeja" aria-current={vista === "bandeja" ? "page" : undefined}>
            Bandeja
          </a>
        </nav>
      </header>
      <main>
        {vista === "registro" ? <Registro /> : <Bandeja />}
      </main>
    </>
  );
}
