import { Component } from '@angular/core';

import { environment } from '../environments/environment';

@Component({
  selector: 'app-root',
  standalone: true,
  template: `
    <main>
      <h1>units-webapp</h1>
      <p>Frontend de démonstration instrumenté avec Grafana Faro (RUM et traces) et GlitchTip (erreurs).</p>

      <div class="actions">
        <button type="button" (click)="appelerBackend()">Appeler le backend</button>
        <button type="button" (click)="declencherErreur()">Déclencher une erreur JS</button>
      </div>

      <p class="hint">
        « Appeler le backend » émet une requête vers units-service ; Faro propage le contexte de trace,
        donc le clic et la requête Django apparaissent comme une seule trace dans Tempo.
      </p>

      <pre>{{ resultat }}</pre>
    </main>
  `,
  styles: [`
    main { max-width: 680px; margin: 3rem auto; padding: 0 1rem; }
    h1 { margin-bottom: .25rem; }
    .actions { display: flex; gap: 1rem; margin: 1.25rem 0; flex-wrap: wrap; }
    button { padding: .6rem 1.1rem; cursor: pointer; border-radius: 6px; border: 1px solid #888; background: transparent; }
    .hint { font-size: .9rem; opacity: .8; }
    pre { background: rgba(128,128,128,.12); padding: 1rem; border-radius: 6px; min-height: 3rem; white-space: pre-wrap; }
  `],
})
export class AppComponent {
  resultat = '';

  async appelerBackend(): Promise<void> {
    this.resultat = 'Appel en cours...';
    try {
      const rep = await fetch(`${environment.apiBase}/demo/commande`);
      this.resultat = JSON.stringify(await rep.json(), null, 2);
    } catch (e) {
      this.resultat = 'Erreur : ' + (e as Error).message;
    }
  }

  declencherErreur(): void {
    // Erreur JS volontaire : captée par Faro (-> Loki) et par GlitchTip si un DSN est configuré.
    throw new Error('Erreur de démonstration déclenchée depuis units-webapp');
  }
}
