// Die nachgebaute Sportgerichtsbarkeit -- der Kleber zwischen den Seiten.
//
// Die Seiten selbst sind stumm: sie tragen die Formen des echten Moduls und
// sonst nichts. Was ein Testfall braucht, steht in der Adresse
// (`?fall=fremd`), und diese Datei reicht es weiter und wendet es an. Ohne das
// braeuchte jede Abweichung einen eigenen Satz Seiten, und sechs Saetze
// Seiten laufen auseinander.
(function () {
  const parameter = new URLSearchParams(location.search);
  const fall = parameter.get("fall") || "";

  // Weiterreichen: jeder Verweis und jedes Formular nimmt die Spielart mit,
  // sonst ist sie nach dem ersten Klick vergessen.
  for (const verweis of document.querySelectorAll("a[href]")) {
    const ziel = new URL(verweis.getAttribute("href"), location.href);
    if (fall) ziel.searchParams.set("fall", fall);
    verweis.setAttribute("href", ziel.pathname + ziel.search);
  }
  for (const formular of document.querySelectorAll("form")) {
    if (!fall) continue;
    const feld = document.createElement("input");
    feld.type = "hidden";
    feld.name = "fall";
    feld.value = fall;
    formular.appendChild(feld);
  }

  // Die Spielkennung wandert durch die Adresse, so wie DFBnet sie durch die
  // Sitzung traegt. Das Formular spiegelt sie in ein gesperrtes Feld -- genau
  // daran erkennt der Lauf, dass er die richtige Akte offen hat.
  const gespiegelt = document.querySelector("input[name='_kontext.fall.spielKennung']");
  if (gespiegelt) {
    gespiegelt.value =
      fall === "fremd" ? "999999999" : parameter.get("kontext.suche.spielkennung") || "";
  }

  // Die Abweichungen. Jede steht hier und nicht in einer eigenen Seite.
  if (fall === "halb") {
    // Das Formular kam nicht vollstaendig hoch: das Tatbestandsfeld fehlt.
    document.querySelectorAll("textarea[name='kontext.currentVorgang.tatbestand']").forEach(
      (feld) => feld.remove(),
    );
  }
  if (fall === "ohne_gericht") {
    // Das Gericht steht nicht zur Auswahl -- etwa, weil das Konto es nicht
    // fuehrt.
    document
      .querySelectorAll("select[name='kontext.fall.sitzung.gericht'] option")
      .forEach((wahl) => {
        if (wahl.value) wahl.remove();
      });
  }
  if (fall === "leer") {
    // Die Suche hat nichts gefunden: keine Zeile, kein Bearbeiten-Symbol.
    document.querySelectorAll("table tbody tr").forEach((zeile) => zeile.remove());
  }
  if (fall === "ohne_nummer") {
    // Gespeichert, aber die Nummer steht nicht auf der Seite. Kommt vor.
    document.querySelectorAll("[data-aktenzeichen]").forEach((stelle) => stelle.remove());
  }
})();
