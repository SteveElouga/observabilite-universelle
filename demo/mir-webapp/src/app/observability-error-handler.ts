import { ErrorHandler, Injectable } from '@angular/core';
import { faro } from '@grafana/faro-web-sdk';
import * as Sentry from '@sentry/angular';

import { environment } from '../environments/environment';

/**
 * Gestionnaire d'erreurs Angular qui remonte les exceptions à l'observabilité.
 *
 * Nécessaire parce qu'Angular intercepte les erreurs dans sa zone : le gestionnaire
 * d'erreurs par défaut de Faro (window.onerror) ne les voit donc pas. On pousse
 * explicitement l'erreur vers Faro (donc Loki), et vers GlitchTip si un DSN est configuré.
 */
@Injectable()
export class ObservabilityErrorHandler implements ErrorHandler {
  handleError(error: unknown): void {
    const err = error instanceof Error ? error : new Error(String(error));

    faro?.api?.pushError(err); // -> récepteur Faro -> Loki (kind=exception)

    if (environment.glitchtipDsn) {
      Sentry.captureException(err); // -> GlitchTip, si un DSN est renseigné
    }

    console.error(error);
  }
}
