// Gráfica de evolución del precio por región y tipo de aceite (Chart.js).
(function () {
  const datos = JSON.parse(document.getElementById("datos-precios").textContent || "{}");
  const regiones = Object.keys(datos);
  if (!regiones.length || !window.Chart) return;

  const TIPOS = [
    { clave: "AOVE", nombre: "Virgen extra (AOVE)", token: "--serie-aove" },
    { clave: "Virgen", nombre: "Virgen", token: "--serie-virgen" },
    { clave: "Lampante", nombre: "Lampante", token: "--serie-lampante" },
  ];
  const RANGOS = { "1M": 30, "3M": 90, "1A": 365, todo: 0 };
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

  // Formateadores reutilizables (Intl) para números y fechas en español.
  const num3 = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  const num2 = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fechaLarga = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short", year: "numeric" });
  const fechaDiaMes = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short" });
  const fechaMesAnio = new Intl.DateTimeFormat("es-ES", { month: "short", year: "2-digit" });
  const aFecha = (iso) => new Date(iso + "T00:00:00");

  Chart.defaults.font.family = 'Outfit, system-ui, sans-serif';
  Chart.defaults.font.size = 13;

  // Estado inicial desde la URL (?region=Italia&periodo=1A), para poder enlazar una vista concreta.
  const params = new URLSearchParams(location.search);
  let region = regiones.includes(params.get("region")) ? params.get("region") : regiones[0];
  let dias = params.get("periodo") in RANGOS ? RANGOS[params.get("periodo")] : 90;
  let diasVisibles = 90; // tramo real de datos en pantalla: decide el formato de fecha del eje

  // Etiqueta directa al final de cada línea (en color de texto; el color identifica la marca).
  const etiquetasFinales = {
    id: "etiquetasFinales",
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      ctx.save();
      ctx.font = '600 12px Outfit, system-ui, sans-serif';
      ctx.fillStyle = css("--texto");
      ctx.textBaseline = "middle";
      const usados = [];
      chart.data.datasets.forEach((ds, i) => {
        const meta = chart.getDatasetMeta(i);
        const p = meta.data[meta.data.length - 1];
        if (!p || meta.hidden) return;
        let y = p.y;
        for (const u of usados) if (Math.abs(u - y) < 14) y = u + (y >= u ? 14 : -14);
        usados.push(y);
        ctx.fillText(num2.format(ds.data[ds.data.length - 1].y), p.x + 8, y);
      });
      ctx.restore();
    },
  };

  // Línea vertical que acompaña al cursor, para leer las tres series en la misma fecha.
  const cruz = {
    id: "cruz",
    beforeDatasetsDraw(chart) {
      const activo = chart.tooltip && chart.tooltip.getActiveElements();
      if (!activo || !activo.length) return;
      const { ctx, chartArea } = chart;
      ctx.save();
      ctx.strokeStyle = css("--tenue");
      ctx.globalAlpha = 0.35;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(activo[0].element.x, chartArea.top);
      ctx.lineTo(activo[0].element.x, chartArea.bottom);
      ctx.stroke();
      ctx.restore();
    },
  };

  function series() {
    const porTipo = datos[region] || {};
    let desde = null;
    if (dias) {
      const ultimas = Object.values(porTipo).map((p) => p[p.length - 1][0]).sort();
      const fin = aFecha(ultimas[ultimas.length - 1]);
      fin.setDate(fin.getDate() - dias);
      desde = `${fin.getFullYear()}-${String(fin.getMonth() + 1).padStart(2, "0")}-${String(fin.getDate()).padStart(2, "0")}`;
    }
    return TIPOS.filter((t) => porTipo[t.clave]).map((t) => ({
      tipo: t,
      puntos: porTipo[t.clave].filter(([f]) => !desde || f >= desde).map(([f, v]) => ({ x: f, y: v })),
    }));
  }

  const grafica = new Chart(document.getElementById("grafica"), {
    type: "line",
    data: { datasets: [] },
    plugins: [etiquetasFinales, cruz],
    options: {
      maintainAspectRatio: false,
      animation: matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 300 },
      layout: { padding: { right: 44, top: 8 } },
      interaction: { mode: "index", intersect: false },
      elements: { line: { borderWidth: 2, tension: 0 }, point: { radius: 0, hoverRadius: 5, hitRadius: 12 } },
      scales: {
        x: {
          type: "time",
          time: { minUnit: "day" },
          grid: { display: false },
          ticks: { maxTicksLimit: 7, callback: (v) => (diasVisibles <= 120 ? fechaDiaMes : fechaMesAnio).format(new Date(v)) },
        },
        y: { border: { display: false }, ticks: { callback: (v) => num2.format(v) + " €" } },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          padding: 12,
          cornerRadius: 8,
          titleFont: { weight: 600 },
          borderWidth: 1,
          boxPadding: 4,
          usePointStyle: true,
          callbacks: {
            title: (items) => (items.length ? fechaLarga.format(aFecha(items[0].raw.x)) : ""),
            label: (c) => ` ${c.dataset.label}: ${num3.format(c.parsed.y)} €/kg`,
          },
        },
      },
    },
  });

  // Gráfica pequeña de la tarjeta de precio: solo el virgen extra, con curva suave y relleno dorado.
  const mini = new Chart(document.getElementById("grafica-mini"), {
    type: "line",
    data: { datasets: [] },
    options: {
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      elements: { line: { borderWidth: 2.5, cubicInterpolationMode: "monotone" }, point: { radius: 0, hoverRadius: 5, hitRadius: 12 } },
      scales: { x: { type: "time", display: false }, y: { display: false } },
      plugins: {
        legend: { display: false },
        tooltip: {
          displayColors: false,
          padding: 8,
          callbacks: {
            title: (items) => (items.length ? fechaLarga.format(aFecha(items[0].raw.x)) : ""),
            label: (c) => `${num3.format(c.parsed.y)} €/kg`,
          },
        },
      },
    },
  });

  function pintarMini(s) {
    const aove = s.find((x) => x.tipo.clave === "AOVE");
    mini.data.datasets = aove ? [{
      data: aove.puntos,
      borderColor: css("--texto"),
      pointHoverBackgroundColor: css("--oro"),
      pointHoverBorderColor: css("--texto"),
      fill: true,
      backgroundColor: ({ chart }) => {
        if (!chart.chartArea) return "transparent";
        const g = chart.ctx.createLinearGradient(0, chart.chartArea.top, 0, chart.chartArea.bottom);
        g.addColorStop(0, "rgba(226, 178, 59, 0.2)");
        g.addColorStop(1, "rgba(226, 178, 59, 0)");
        return g;
      },
    }] : [];
    Object.assign(mini.options.plugins.tooltip, { backgroundColor: css("--boton"), titleColor: css("--boton-texto"), bodyColor: css("--boton-texto") });
    mini.update();
  }

  // Colores del tema actual (se vuelven a leer si el sistema pasa a modo claro u oscuro).
  function aplicarTema() {
    const o = grafica.options;
    o.scales.x.ticks.color = o.scales.y.ticks.color = css("--tenue");
    o.scales.x.border = { color: css("--linea") };
    o.scales.y.grid = { color: css("--rejilla") };
    Object.assign(o.plugins.tooltip, {
      backgroundColor: css("--superficie"),
      titleColor: css("--texto"),
      bodyColor: css("--texto"),
      borderColor: css("--linea"),
    });
  }

  function pintar() {
    const s = series();
    const todas = s.flatMap((x) => x.puntos.map((p) => p.x)).sort();
    diasVisibles = todas.length ? (aFecha(todas[todas.length - 1]) - aFecha(todas[0])) / 864e5 : 0;
    grafica.data.datasets = s.map(({ tipo, puntos }) => ({
      label: tipo.nombre,
      data: puntos,
      borderColor: css(tipo.token),
      backgroundColor: css(tipo.token),
      pointBackgroundColor: css(tipo.token),
      pointBorderColor: css("--superficie"),
      pointHoverBorderWidth: 2,
    }));
    grafica.update();
    pintarMini(s);

    document.getElementById("grafica-region").textContent = region;
    document.getElementById("leyenda").innerHTML = s
      .map(({ tipo }) => `<span><i style="background:var(${tipo.token})"></i>${tipo.nombre}</span>`)
      .join("");

    // Tabla accesible con los mismos datos (más reciente primero)
    const fechas = [...new Set(s.flatMap((x) => x.puntos.map((p) => p.x)))].sort().reverse();
    const mapa = s.map((x) => Object.fromEntries(x.puntos.map((p) => [p.x, p.y])));
    document.getElementById("tabla-datos").innerHTML =
      `<thead><tr><th>Fecha</th>${s.map((x) => `<th class="num">${x.tipo.nombre}</th>`).join("")}</tr></thead><tbody>` +
      fechas.map((f) => `<tr><td>${fechaLarga.format(aFecha(f))}</td>${mapa.map((m) => `<td class="num">${m[f] != null ? num3.format(m[f]) : "—"}</td>`).join("")}</tr>`).join("") +
      "</tbody>";
  }

  function sincronizar() {
    document.querySelectorAll(".region").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.region === region)));
    document.querySelectorAll(".rango").forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.dias) === dias)));
    document.querySelectorAll("[data-region-panel]").forEach((p) => (p.hidden = p.dataset.regionPanel !== region));
    const url = new URL(location.href);
    url.searchParams.set("region", region);
    url.searchParams.set("periodo", Object.keys(RANGOS).find((k) => RANGOS[k] === dias));
    history.replaceState(null, "", url);
  }

  document.querySelectorAll(".region").forEach((b) =>
    b.addEventListener("click", () => {
      region = b.dataset.region;
      sincronizar();
      pintar();
    })
  );
  document.querySelectorAll(".rango").forEach((b) =>
    b.addEventListener("click", () => {
      dias = Number(b.dataset.dias);
      sincronizar();
      pintar();
    })
  );
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    aplicarTema();
    pintar();
  });

  aplicarTema();
  if (params.has("region") || params.has("periodo")) sincronizar();
  pintar();
  // La tipografía web llega después del primer dibujo: se repinta para medir bien ejes y etiquetas.
  if (document.fonts) document.fonts.ready.then(() => grafica.update());
})();
