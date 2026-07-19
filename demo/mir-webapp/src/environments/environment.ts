/**
 * Configuration de la démo mir-webapp.
 * Valeurs par défaut pour un accès local (http://localhost:8090).
 * Le récepteur Faro d'Alloy accepte le CORS (§10.4), donc l'appel direct fonctionne.
 * L'appel backend passe par le proxy nginx (/api), donc même origine, pas de CORS.
 */
export const environment = {
  appVersion: '0.1.0',
  env: 'demo',
  faroUrl: 'http://localhost:12347/collect', // récepteur Faro d'Alloy (port publié sur l'hôte)
  apiBase: '/api',                           // proxifié par nginx vers units-service:8000
  glitchtipDsn: '',                          // renseigner avec un DSN de projet GlitchTip pour activer le suivi d'erreurs
};
