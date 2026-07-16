// Cloudflare Worker — déclenche le workflow GitHub Actions "Ticket monitor"
// toutes les 5 minutes via l'API repository_dispatch.
//
// Variables d'environnement (à configurer dans Cloudflare > Settings > Variables) :
//   GITHUB_OWNER : "WaveRoro"
//   GITHUB_REPO  : "ticket-monitor"
//   GITHUB_TOKEN : (encrypted) — PAT fine-grained avec permission Contents: write sur le repo
//
// Cron trigger (à configurer dans Cloudflare > Settings > Triggers) :
//   */5 * * * *

export default {
  async scheduled(event, env, ctx) {
    const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/dispatches`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ticket-monitor-cron-trigger",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ event_type: "ticket-check" }),
    });

    if (!response.ok) {
      const text = await response.text();
      console.error(`dispatch failed: HTTP ${response.status} - ${text}`);
      throw new Error(`GitHub API returned ${response.status}`);
    }
    console.log(`dispatch OK at ${new Date().toISOString()}`);
  },

  // Réponse à une visite HTTP directe du Worker (utile pour un test manuel dans le navigateur)
  async fetch(request, env, ctx) {
    return new Response(
      "Ticket monitor cron trigger.\n" +
      "Runs on schedule (see Cloudflare cron trigger settings), not on HTTP requests.\n" +
      "Last deployed: " + new Date().toISOString(),
      { status: 200, headers: { "Content-Type": "text/plain; charset=utf-8" } }
    );
  },
};
