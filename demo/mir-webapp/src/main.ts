import { bootstrapApplication } from '@angular/platform-browser';
import { initializeFaro, getWebInstrumentations } from '@grafana/faro-web-sdk';
import { TracingInstrumentation } from '@grafana/faro-web-tracing';

import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';
import { environment } from './environments/environment';

// Faro (RUM), initialisé AVANT le bootstrap Angular (§10.2) :
//  - getWebInstrumentations : Web Vitals, erreurs JS, logs console, sessions,
//  - TracingInstrumentation : traces des appels fetch/XHR, avec propagation W3C (traceparent)
//    jusqu'au backend -> la trace navigateur et la trace Django ne font qu'une.
initializeFaro({
  url: environment.faroUrl,
  app: { name: 'mir-webapp', version: environment.appVersion, environment: environment.env },
  instrumentations: [
    ...getWebInstrumentations(),
    new TracingInstrumentation(),
  ],
});

bootstrapApplication(AppComponent, appConfig).catch((err) => console.error(err));
