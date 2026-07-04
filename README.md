<p align="center"><img width=60% src="docs/header.png"></p>

<p align="center">
  <b>Générateur d'adresses email iCloud « HideMyEmail »</b><br>
  Crée et gère des alias email Apple, à un rythme sûr pour ne pas faire bloquer ton compte.
</p>

> ⚠️ Il faut un abonnement **iCloud+ actif** pour pouvoir générer des adresses iCloud.

---

## 📑 Sommaire

- [En bref](#-en-bref)
- [Installation](#-installation)
- [Activer ta clé d'accès](#-activer-ta-clé-daccès)
- [Récupérer ton cookie iCloud](#-récupérer-ton-cookie-icloud)
- [Lancer l'application (menu interactif)](#-lancer-lapplication-menu-interactif)
- [Générer des alias](#-générer-des-alias)
- [Lister / exporter tes alias](#-lister--exporter-tes-alias)
- [Mode ligne de commande](#-mode-ligne-de-commande-rapide)
- [Plusieurs comptes iCloud](#-plusieurs-comptes-icloud)
- [Mettre à jour](#-mettre-à-jour-le-projet)
- [FAQ](#-faq)

---

## 🚀 En bref

- 🛡️ **Rythme sûr et « humain » par défaut** : jamais plus de **5 alias/heure** ni plus de **15 alias/jour**, sauf si tu actives volontairement le mode override (voir plus bas). Les générations sont étalées dans le temps, de façon aléatoire, pour imiter un humain et éviter que ton compte iCloud soit signalé.
- 🧭 **Menu interactif** : lance l'app sans rien connaître, elle te guide pas à pas.
- ⏳ **Compte à rebours en direct**, alias par alias, avec le nombre d'alias **restants** affiché à chaque instant (y compris en multi-comptes, avec un tableau de bord par compte).
- 📊 **Compteur du jour** : à chaque lancement, l'outil te dit combien d'alias ont déjà été générés aujourd'hui (par compte) et réduit automatiquement ce qu'il te reste à générer pour rester sous la limite/jour.
- 👥 **Multi-comptes** : gère 1 ou plusieurs comptes iCloud en parallèle.
- 🔑 **Clé d'accès** pour utiliser l'outil (vérification 100 % hors-ligne).

---

## 📦 Installation

> Python **3.12+** requis.

**1. Cloner le dépôt**

```bash
git clone https://github.com/usedev00-spec/mail-gen
cd mail-gen
```

**2. Installer les dépendances**

```bash
pip install -r requirements.txt
```

---

## 🔑 Activer ta clé d'accès

L'outil nécessite une **clé d'accès** (fournie par l'auteur). Tu n'as à le faire **qu'une seule fois** :

```bash
python3 cli.py activate TA_CLE_ICI
```

Résultat :

```text
✓ Access key activated for client-01 (expires: never).
```

La clé est enregistrée dans `~/.hidemyemail/license.key` et réutilisée automatiquement à chaque lancement.

> 💡 Tu peux aussi définir la clé via une variable d'environnement, sans activer :
> ```bash
> export HIDEMYEMAIL_KEY="TA_CLE_ICI"
> ```
> Si aucune clé valide n'est trouvée, l'application te la demandera au démarrage.

---

## 🍪 Récupérer ton cookie iCloud

Pour communiquer avec Apple, l'outil a besoin de ton cookie de session iCloud. Tous tes cookies vivent dans **un seul dossier, [`cookies/`](./cookies)** — simple à retenir, et tu peux les nommer comme tu veux.

À faire **une seule fois** par compte iCloud 🙂

1. Installe l'extension Chrome **[EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)**

2. Dans ses réglages, choisis le format d'export **`Semicolon separated name=value pairs`**

<p align="center"><img src="docs/cookie-settings.png" width=70%></p>

3. Va sur **[les réglages iCloud](https://www.icloud.com/settings/)** dans ton navigateur et connecte-toi

4. Clique sur l'extension EditThisCookie et **exporte** les cookies

<p align="center"><img src="docs/export-cookies.png" width=70%></p>

5. Colle le contenu exporté dans un fichier **à l'intérieur du dossier `cookies/`** :
   - Pour ton compte principal (celui utilisé par défaut, sans `--accounts-file`) : **`cookies/cookie.txt`**.
   - Pour un compte supplémentaire (multi-comptes) : **n'importe quel nom**, ex. `cookies/perso.txt`, `cookies/boulot.txt` — tant que ça finit en `.txt` et que tu réutilises ce nom dans `accounts.json` (voir [Plusieurs comptes iCloud](#-plusieurs-comptes-icloud)).

Le dépôt fournit des **modèles suivis par git** dans ce même dossier — [`cookies/cookie.example.txt`](./cookies/cookie.example.txt), [`cookies/secondary.example.txt`](./cookies/secondary.example.txt), [`cookies/third.example.txt`](./cookies/third.example.txt) — mis à jour à chaque `git pull`. Le plus simple : copie un modèle, renomme-le sans `.example`, et colle-y ton vrai cookie.

> 🔒 **Tout le contenu réel de `cookies/` est ignoré par git**, quel que soit le nom que tu choisis (seuls les `*.example.txt` sont suivis) : tes cookies ne seront jamais envoyés en ligne, et un `git pull` ne touchera jamais tes vrais fichiers.

---

## 🧭 Lancer l'application (menu interactif)

La façon la plus simple : lance le CLI **sans argument**, un menu s'affiche.

**Sur Mac / Linux :**
```bash
python3 cli.py
```

**Sur Windows :**
```bash
python cli.py
```

Tu verras ceci :

```text
╭────────────────────────────────────────────────────────╮
│                                                          │
│                  📧  iCloud HideMyEmail                  │
│           Generate & manage your email aliases           │
│                                                          │
╰────────────────────────────────────────────────────────╯
╭─────────────────────── Menu ───────────────────────╮
│   [1]    Generate    Create new HideMyEmail aliases  │
│   [2]    List        Browse & export existing aliases│
│   [0]    Quit        Exit the program                │
╰─────────────────────────────────────────────────────╯
Select an option [1/2/0] (1):
```

- **1** → Générer de nouveaux alias
- **2** → Lister / exporter tes alias existants
- **0** → Quitter

Tape le numéro et appuie sur **Entrée**.

---

## ✨ Générer des alias

Choisis **`1`** dans le menu. L'outil te pose 3 questions simples, puis affiche un récapitulatif avant de lancer :

```text
──────────────────────── Generate aliases ────────────────────────
Aliases are generated at a safe, human pace (max 5/hour, 15/day)
spread over the run.

Override the safe limits (5/hour, 15/day)? Not recommended. [y/n] (n): n

How many aliases do you want to generate? (5): 10
Maximum aliases per calendar day? (15): 15
Spread the run over how many hours? (3.0): 8
Use a multi-account JSON file? [y/n] (n): n

╭──────────────────── Review ────────────────────╮
│         Aliases    10                           │
│    Max per hour    5/hour                       │
│     Daily limit    15/day                       │
│        Duration    8 h                          │
│            Pace    ~1.3/hour                     │
│        Override    off (safe defaults)          │
│   Accounts file    —                            │
╰─────────────────────────────────────────────────╯
Proceed? [y/n] (y): y
```

Que veulent dire les questions ?

| Question | Signification |
|---|---|
| **Override the safe limits…** | Active volontairement le mode risqué (voir ci-dessous). Par défaut : non. |
| **How many aliases…** | Combien d'alias tu veux créer au total |
| **Maximum… per calendar day** | Plafond d'alias par jour calendaire (15 par défaut, en sécurité) |
| **Spread the run over how many hours** | Sur combien d'heures étaler la génération |

Avant de démarrer, l'outil te dit combien d'alias tu as **déjà générés aujourd'hui** (lu depuis l'historique local `generation_log.jsonl`) et réduit le nombre à générer si besoin pour rester sous la limite/jour :

```text
[00:38:56] 3 alias(es) already generated today (calendar day, limit 15/day).
[00:38:56] Generating 10 alias(es) over ~8h 42m 8s (max 5/hour, 15/day).
```

Ensuite, un **compte à rebours en direct** s'affiche entre chaque alias, avec le nombre d'alias **restants** :

```text
⠹ Alias 1/10 (10 remaining) — next at 01:25:43 in 46m 47s
```

> ⏳ **Laisse la fenêtre ouverte** pendant toute la durée du run : étaler les alias dans le temps est exactement ce qui protège ton compte.

### 🛡️ Le garde-fou anti-blocage

Si tu demandes un rythme trop rapide (ex. 15 alias en 1 h), l'outil **te prévient** et **rallonge automatiquement** le run pour rester sous la limite :

```text
⚠ The requested 1h 0m 0s window is too short to stay within 5/hour
  and 15/day. The run will be automatically extended to about
  2h 7m 0s to protect the account.
Proceed? [y/n] (n):
```

### ⚠️ Mode override (à tes risques)

Par défaut, **impossible de dépasser 5/heure et 15/jour**, même si tu tapes un chiffre plus grand dans un prompt : la valeur est automatiquement ramenée (« clamped ») à la limite sûre, avec un message clair.

Pour dépasser ces limites en connaissance de cause :

- **Menu interactif** : réponds `y` à *« Override the safe limits… »*. Un avertissement rouge s'affiche, puis tu peux choisir un rythme horaire et un plafond journalier plus élevés.
- **Ligne de commande** : ajoute `--override-limits`, avec éventuellement `--daily-limit` et `--max-per-hour` :
  ```bash
  python3 cli.py generate --count 50 --daily-limit 40 --max-per-hour 10 --override-limits
  ```

Sans `--override-limits`, `--daily-limit 40` et `--max-per-hour 10` seraient silencieusement ramenés à 15 et 5. Le flag doit être **explicite** — ce n'est jamais activé par accident.

> ⚠️ Dépasser le rythme sûr augmente le risque de rate-limit, de blocage temporaire ou d'autre restriction sur le compte iCloud/Apple. À utiliser à tes propres risques.

---

## 📋 Lister / exporter tes alias

Choisis **`2`** dans le menu (ou `python3 cli.py list`). L'outil affiche d'abord le total exact renvoyé par Apple pour ce compte (pratique pour vérifier que rien ne manque), puis un tableau :

```text
[00:38:56] Apple returned 662 alias(es) total for this account (662 active,
           0 inactive) — fetched in a single call, no pagination.
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Label    ┃ Hide my email        ┃ Created Date Time   ┃ IsActive ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ shopping │ ab.cd@icloud.com     │ 2026-06-21 12:30:00 │ True     │
│ newsletr │ ef.gh@icloud.com     │ 2026-06-20 09:15:00 │ True     │
└──────────┴──────────────────────┴─────────────────────┴──────────┘
```

Ce total est **toujours complet** (un seul appel API, sans pagination). S'il te semble inférieur à ce que tu vois ailleurs, voir la FAQ *« J'ai plus d'adresses dans Réglages iCloud sur mon iPhone »* ci-dessous.

Tu peux **exporter en CSV** : le menu te le propose, ou en ligne de commande :

```bash
python3 cli.py list --export mes_alias.csv
```

---

## ⚡ Mode ligne de commande (rapide)

Si tu préfères tout passer en une commande, sans le menu :

```bash
# 15 alias étalés sur 4 heures (≈ 4/heure)
python3 cli.py generate --count 15 --duration 4

# laisse l'outil choisir une durée sûre, plafond à 15/jour (défaut)
python3 cli.py generate --count 15

# dépasse volontairement les limites sûres (à tes risques)
python3 cli.py generate --count 50 --daily-limit 40 --max-per-hour 10 --override-limits

# lister les alias actifs
python3 cli.py list

# afficher l'aide
python3 cli.py --help
python3 cli.py generate --help
```

| Option | Rôle |
|---|---|
| `--count` | Nombre d'alias à générer |
| `--daily-limit` | Maximum d'alias par jour (défaut et plafond sûr : 15, sauf `--override-limits`) |
| `--max-per-hour` | Maximum d'alias par heure glissante (défaut et plafond sûr : 5, sauf `--override-limits`) |
| `--override-limits` | Active volontairement le dépassement des limites sûres, à tes risques |
| `--duration` | Nombre d'heures pour étaler le run (sinon, rythme sûr automatique) |
| `--accounts-file` | Fichier JSON multi-comptes (voir ci-dessous) |

---

## 👥 Plusieurs comptes iCloud

Tu peux gérer plusieurs comptes **en parallèle** avec un fichier JSON. Pars de [`accounts.example.json`](./accounts.example.json) pour créer ton `accounts.json` :

```json
[
  {
    "name": "main",
    "cookie_file": "cookies/cookie.txt"
  },
  {
    "name": "secondary",
    "cookie_file": "cookies/secondary.txt"
  },
  {
    "name": "third",
    "cookie_file": "cookies/third.txt"
  }
]
```

Chaque `cookie_file` pointe vers un fichier du dossier **[`cookies/`](./cookies)** (voir [Récupérer ton cookie iCloud](#-récupérer-ton-cookie-icloud) pour comment les créer) — tu peux les nommer comme tu veux, `name` et `cookie_file` n'ont pas besoin de correspondre.

À savoir sur `accounts.json` :

- Chaque compte n'a que **deux champs**, tous les deux obligatoires : `name` (un nom pour l'identifier dans les logs) et `cookie_file` (le chemin de son cookie iCloud, en général dans `cookies/`).
- **Aucune limite ne se configure par compte.** Le nombre d'alias, la limite/jour, le rythme/heure et l'override s'appliquent **globalement**, via `--count`, `--daily-limit`, `--max-per-hour` et `--override-limits` (ou les prompts du menu) — les mêmes réglages pour tous les comptes du fichier.
- Tous les comptes tournent **en parallèle**, chacun respectant les mêmes limites sûres par défaut (5/heure, 15/jour), et chacun avec son propre compteur de génération du jour (voir plus bas).
- Les chemins relatifs sont résolus depuis le dossier qui contient `accounts.json`.
- `accounts.json` est **ignoré par git** : jamais poussé en ligne (seul `accounts.example.json` est suivi).
- Si `accounts.json` est mal formé, s'il manque `name` ou `cookie_file` sur un compte, ou si un `cookie_file` référencé n'existe pas, l'outil affiche une erreur claire et s'arrête proprement (pas de stacktrace).

```bash
# Générer pour tous les comptes du fichier (--count obligatoire pour le multi-compte)
python3 cli.py generate --accounts-file accounts.json --count 15

# Lister sur tous les comptes, avec export
python3 cli.py list --accounts-file accounts.json --export tous_les_comptes.csv
```

Pendant la génération multi-comptes, un **tableau de bord en direct** affiche une ligne par compte avec son propre compte à rebours :

```text
(main)       Alias 2/10 (8 remaining) — next at 01:12:04 in 12m 3s
(secondary)  Alias 1/5 (5 remaining) — next at 01:05:30 in 5m 29s
```

---

## 🔄 Mettre à jour le projet

```bash
git checkout main
git pull --ff-only origin main
```

> Si tu as des modifications locales, fais un `git stash` (ou un commit) avant de tirer.

---

## ❓ FAQ

**Combien d'alias puis-je créer ?**
Apple autorise environ 5 alias toutes les ~30 min, et plafonne autour de ~700 au total. L'outil respecte automatiquement ≤ 5/heure pour rester safe.

**L'application me demande une clé d'accès, c'est normal ?**
Oui. Active-la une fois avec `python3 cli.py activate TA_CLE`. Voir [Activer ta clé d'accès](#-activer-ta-clé-daccès).

**« An access key is required » ou « Invalid or expired key »**
Ta clé est manquante, mal copiée ou expirée. Recolle-la entièrement, ou demande une nouvelle clé à l'auteur.

**« Missing cookies/cookie.txt » / erreur de session Apple**
Ton cookie est absent ou périmé. Réexporte un cookie frais depuis [iCloud](https://www.icloud.com/settings/) et recolle-le dans `cookies/cookie.txt` (ou le fichier du compte concerné dans `cookies/`).

**Pourquoi ça prend des heures ?**
C'est volontaire : étaler les générations protège ton compte. Réduis le nombre d'alias ou augmente la durée pour un rythme plus tranquille.

**« Today's safe daily limit has already been reached »**
Tu as relancé l'outil le même jour calendaire après avoir déjà atteint ta limite/jour (ex. 15). C'est volontaire : la limite/jour s'applique **par compte, sur toute la journée**, même en plusieurs lancements, pas juste dans un seul run. L'historique est lu depuis `generation_log.jsonl` (local, ignoré par git). Réessaie demain, ou passe `--override-limits` à tes risques.

**J'ai plus d'adresses dans Réglages > iCloud sur mon iPhone que dans l'export de l'outil**
C'est normal, et ce n'est pas un bug de fetch : chaque `list`/export affiche désormais le total exact renvoyé par Apple (`Apple returned N alias(es) total...`), et ce total est complet — vérifié, aucune pagination côté serveur. L'écart vient d'ailleurs : l'écran iPhone **Réglages > [ton nom] > iCloud > Masquer mon adresse e-mail** regroupe aussi les adresses créées automatiquement via **« Se connecter avec Apple »** (une par appli où tu l'as utilisé). Ce sont des alias qui viennent d'un système Apple différent (`appleid.apple.com`, pas `icloud.com`) et que cet outil ne gère pas — reconnaissables sur iPhone à leur libellé du style *« Utilisé avec [nom de l'appli] »*.

---

## 📄 Licence

Sous licence MIT — voir le fichier [LICENSE](./LICENSE).
