# Instagram Followers Scraper

Microservice d'analyse des followers Instagram. Identifie les comptes influents (>N followers) parmi les abonnés d'un compte public, avec support de profondeur récursive.

## Prérequis

- Docker et Docker Compose
- Compte Instagram valide

## Installation

```bash
cp .env.example .env
# Configurer INSTAGRAM_USERNAME et INSTAGRAM_PASSWORD dans .env
```

## Lancement

```bash
docker compose up -d
```

Le service est accessible sur `http://localhost:8001`.

## API

### POST /analyze

Lance une analyse asynchrone.

```bash
curl -X POST http://localhost:8001/analyze \
  -H "Content-Type: application/json" \
  -d '{"username": "compte_cible", "depth": 1}'
```

Paramètres :
- `username` (requis) : compte Instagram public à analyser
- `depth` (optionnel) : profondeur de récursion (défaut: 1)

### GET /analyze/{job_id}

Récupère le statut et les résultats d'un job.

```bash
curl http://localhost:8001/analyze/{job_id}
```

### GET /health

Health check du service.

## Configuration

| Variable | Description | Défaut |
|----------|-------------|--------|
| INSTAGRAM_USERNAME | Identifiant Instagram | - |
| INSTAGRAM_PASSWORD | Mot de passe | - |
| MIN_FOLLOWERS | Seuil minimum de followers | 3000 |
| MAX_DEPTH | Profondeur maximale | 3 |

## Session Instagram

Pour les comptes avec 2FA, générer une session manuellement :

```bash
python scripts/login.py
```

Le fichier `session.json` sera monté dans le container.

## Exemple de réponse

```json
{
  "job_id": "uuid",
  "status": "completed",
  "target_username": "compte_cible",
  "depth": 1,
  "min_followers": 3000,
  "results": [
    {
      "username": "influenceur",
      "full_name": "Nom Complet",
      "follower_count": 5000,
      "following_count": 200,
      "is_private": false,
      "depth": 1
    }
  ]
}
```