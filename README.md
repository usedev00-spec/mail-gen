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

- 🛡️ **Rythme sûr et « humain »** : jamais plus de **5 alias/heure** ni plus que ta **limite par jour** (≤ 25 conseillé). Les générations sont étalées dans le temps, de façon aléatoire, pour imiter un humain et éviter que ton compte iCloud soit signalé.
- 🧭 **Menu interactif** : lance l'app sans rien connaître, elle te guide pas à pas.
- ⏳ **Compte à rebours en direct** entre chaque alias.
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
✓ Access key activated for pierre (expires: never).
```

La clé est enregistrée dans `~/.hidemyemail/license.key` et réutilisée automatiquement à chaque lancement.

> 💡 Tu peux aussi définir la clé via une variable d'environnement, sans activer :
> ```bash
> export HIDEMYEMAIL_KEY="TA_CLE_ICI"
> ```
> Si aucune clé valide n'est trouvée, l'application te la demandera au démarrage.

---

## 🍪 Récupérer ton cookie iCloud

Pour communiquer avec Apple, l'outil a besoin de ton cookie de session iCloud. À faire **une seule fois** 🙂

1. Installe l'extension Chrome **[EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)**

2. Dans ses réglages, choisis le format d'export **`Semicolon separated name=value pairs`**

<p align="center"><img src="docs/cookie-settings.png" width=70%></p>

3. Va sur **[les réglages iCloud](https://www.icloud.com/settings/)** dans ton navigateur et connecte-toi

4. Clique sur l'extension EditThisCookie et **exporte** les cookies

<p align="center"><img src="docs/export-cookies.png" width=70%></p>

5. Colle le contenu exporté dans un fichier nommé **`cookie.txt`** à la racine du projet.

> 🔒 `cookie.txt` est privé et **ignoré par git** : il ne sera jamais envoyé en ligne.

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
Aliases are generated at a safe, human pace (max 5/hour, 25/day)
spread over the run.

How many aliases do you want to generate? (5): 10
Maximum aliases per calendar day? (25): 25
Spread the run over how many hours? (3.0): 8
Use a multi-account JSON file? [y/n] (n): n

╭──────────────────── Review ────────────────────╮
│         Aliases    10                           │
│     Daily limit    25/day                       │
│        Duration    8 h                          │
│            Pace    ~1.3/hour                     │
│   Accounts file    —                            │
╰─────────────────────────────────────────────────╯
Proceed? [y/n] (y): y
```

Que veulent dire les 3 questions ?

| Question | Signification |
|---|---|
| **How many aliases…** | Combien d'alias tu veux créer au total |
| **Maximum… per calendar day** | Plafond d'alias par jour calendaire (25 conseillé) |
| **Spread the run over how many hours** | Sur combien d'heures étaler la génération |

Ensuite, un **compte à rebours en direct** s'affiche entre chaque alias :

```text
[00:38:56] Generating 10 alias(es) over ~8h 42m 8s (max 5/hour, 25/day).

⠹ Next alias [1/10] at 01:25:43 — 46m 47s remaining
```

> ⏳ **Laisse la fenêtre ouverte** pendant toute la durée du run : étaler les alias dans le temps est exactement ce qui protège ton compte.

### 🛡️ Le garde-fou anti-blocage

Si tu demandes un rythme trop rapide (ex. 15 alias en 1 h), l'outil **te prévient** et **rallonge automatiquement** le run pour rester sous la limite :

```text
⚠ The requested 1h 0m 0s window is too short to stay within 5/hour
  and 25/day. The run will be automatically extended to about
  2h 7m 0s to protect the account.
Proceed? [y/n] (n):
```

---

## 📋 Lister / exporter tes alias

Choisis **`2`** dans le menu (ou `python3 cli.py list`). Tu obtiens un tableau :

```text
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Label    ┃ Hide my email        ┃ Created Date Time   ┃ IsActive ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ shopping │ ab.cd@icloud.com     │ 2026-06-21 12:30:00 │ True     │
│ newsletr │ ef.gh@icloud.com     │ 2026-06-20 09:15:00 │ True     │
└──────────┴──────────────────────┴─────────────────────┴──────────┘
```

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

# laisse l'outil choisir une durée sûre, plafond à 25/jour
python3 cli.py generate --count 25 --daily-limit 25

# lister les alias actifs
python3 cli.py list

# afficher l'aide
python3 cli.py --help
python3 cli.py generate --help
```

| Option | Rôle |
|---|---|
| `--count` | Nombre d'alias à générer |
| `--daily-limit` | Maximum d'alias par jour (défaut : 25) |
| `--duration` | Nombre d'heures pour étaler le run (sinon, rythme sûr automatique) |
| `--accounts-file` | Fichier JSON multi-comptes (voir ci-dessous) |

---

## 👥 Plusieurs comptes iCloud

Tu peux gérer plusieurs comptes **en parallèle** avec un fichier JSON. Pars de [`accounts.example.json`](./accounts.example.json) pour créer ton `accounts.json` :

```json
[
  {
    "name": "principal",
    "cookie_file": "cookies/principal.txt",
    "count": 15,
    "daily_limit": 25,
    "duration_hours": 4
  },
  {
    "name": "secondaire",
    "cookie_file": "cookies/secondaire.txt",
    "count": 5
  }
]
```

À savoir :

- `cookie_file` est **obligatoire** (chemin du cookie de ce compte).
- `count`, `daily_limit`, `duration_hours` sont **optionnels** : s'ils manquent, les valeurs du CLI (`--count`, `--daily-limit`, `--duration`) sont utilisées.
- Chaque compte est **limité indépendamment** (≤ 5/heure et ≤ sa limite/jour), et tous tournent **en parallèle**.
- Les chemins relatifs sont résolus depuis le dossier qui contient `accounts.json`.

```bash
# Générer pour tous les comptes du fichier
python3 cli.py generate --accounts-file accounts.json

# Lister sur tous les comptes, avec export
python3 cli.py list --accounts-file accounts.json --export tous_les_comptes.csv
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

**« Missing cookie.txt » / erreur de session Apple**
Ton cookie est absent ou périmé. Réexporte un cookie frais depuis [iCloud](https://www.icloud.com/settings/) et recolle-le dans `cookie.txt`.

**Pourquoi ça prend des heures ?**
C'est volontaire : étaler les générations protège ton compte. Réduis le nombre d'alias ou augmente la durée pour un rythme plus tranquille.

---

## 📄 Licence

Sous licence MIT — voir le fichier [LICENSE](./LICENSE).
