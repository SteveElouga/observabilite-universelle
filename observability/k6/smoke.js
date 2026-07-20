// k6/smoke.js — parcours synthétique minimal (§10.7).
// Rejoue le trafic type d'un utilisateur sur la démo units-service et vérifie que la
// plateforme reste dans ses seuils de latence et d'erreur. Utile en local (recette) et,
// plus tard, en CI comme job planifié (backlog #10).
//
// À la main :   k6 run k6/smoke.js
// Autre cible : BASE_URL=https://app.example.com k6 run k6/smoke.js
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8088';

export const options = {
  vus: 5,
  duration: '1m',
  thresholds: {
    http_req_duration: ['p(95)<500'],   // 95 % des requêtes sous 500 ms
    http_req_failed: ['rate<0.01'],     // moins de 1 % d'échecs
  },
};

export default function () {
  // Sonde de vivacité
  const sante = http.get(`${BASE_URL}/sante/`);
  check(sante, { 'sante 200': (r) => r.status === 200 });

  // Parcours métier : émet trace + métrique + log corrélés côté units-service
  const commande = http.get(`${BASE_URL}/demo/commande`);
  check(commande, { 'commande 200': (r) => r.status === 200 });

  sleep(1);
}
