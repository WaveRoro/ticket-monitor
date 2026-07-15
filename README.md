# Ticket monitor

Bot de surveillance de disponibilité de billets. Deux modes :

- **Ticketmaster** : appels à la Discovery API officielle, détecte `offsale → onsale` etc.
- **Scraper générique** : polling respectueux d'une page publique, détection par mots-clés OU par hash (avec diff en clair dans la notif).

Notifications : webhook Discord.
Déploiement : GitHub Actions (cron 15 min, état persisté par commit).

## Ajouter un événement

Édite [`events.yaml`](events.yaml). Les entrées commentées en haut du fichier servent de gabarit.

Points clés :
- `id` doit être unique et stable (il sert de clé de persistance dans `state.json`).
- Pour un scraper : commence par `method: keywords` si tu identifies clairement les mots "Complet" / "Acheter" dans la zone. Sinon `method: hash` sur un `selector` bien ciblé.
- `selector` accepte du CSS BeautifulSoup (`#id`, `.classe`, `div.foo > a`, …).

## Dev local

```bash
cd ticket_monitor
python -m venv .venv
.venv\Scripts\activate           # Windows PowerShell : .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env           # puis remplis les valeurs
python -m src.main
```

## Sécurité des clés

- **Jamais** de clé en clair dans le code ou dans `events.yaml`.
- Local : `.env` (déjà dans `.gitignore`).
- GitHub Actions : Settings → Secrets and variables → Actions → New repository secret :
  - `TICKETMASTER_API_KEY`
  - `DISCORD_WEBHOOK_URL`

## Ce que le bot ne fait pas

- Aucun achat, aucune réservation automatique.
- Aucun contournement de CAPTCHA / anti-bot / login.
- Respecte `robots.txt` (vérifié avant chaque requête scraper).
- User-agent honnête (`TicketMonitorBot/1.0`) — un site qui refuse ce UA est considéré comme "ne veut pas être scrapé", et laissé tranquille.
