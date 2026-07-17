// k6/smoke.js — parcours minimal (§10.7), exécutable en CI (job planifié) ou à la main :
//   k6 run k6/smoke.js
// ← Adaptez l'URL cible à votre application.
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 5, duration: '1m',
  thresholds: { http_req_duration: ['p(95)<500'], http_req_failed: ['rate<0.01'] },
};
export default function () {
  const res = http.get('https://app.example.com/health');
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(1);
}
