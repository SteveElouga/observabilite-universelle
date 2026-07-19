import { ApplicationConfig, ErrorHandler } from '@angular/core';
import * as Sentry from '@sentry/angular';

import { environment } from '../environments/environment';

// GlitchTip via le SDK Sentry (drop-in, §4.6). Initialisé uniquement si un DSN est fourni,
// pour que la démo tourne aussi sans GlitchTip configuré (les erreurs restent captées par Faro).
if (environment.glitchtipDsn) {
  Sentry.init({
    dsn: environment.glitchtipDsn,
    release: environment.appVersion,
    environment: environment.env,
    tracesSampleRate: 0, // le tracing est déjà porté par Faro
  });
}

export const appConfig: ApplicationConfig = {
  providers: environment.glitchtipDsn
    ? [{ provide: ErrorHandler, useValue: Sentry.createErrorHandler() }]
    : [],
};
