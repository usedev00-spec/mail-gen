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
- [Détecter, désactiver & supprimer les alias bannis Amazon](#-détecter-désactiver--supprimer-les-alias-bannis-amazon)
- [Mettre à jour](#-mettre-à-jour-le-projet)
- [FAQ](#-faq)
- [Annexe : tout installer de zéro (macOS & Windows)](#-annexe--tout-installer-de-zéro-macos--windows)

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

> Python **3.12+** requis — testé de bout en bout sur **3.13** (dernière version stable vérifiée : suite de tests complète + smoke CLI, aucune API dépréciée).

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

Choisis **`1`** dans le menu. L'outil te pose quelques questions simples, puis affiche un récapitulatif avant de lancer :

```text
──────────────────────── Generate aliases ────────────────────────
Aliases are generated at a safe, human pace (max 5/hour, 15/day)
spread over the run.

Override the safe limits (5/hour, 15/day)? Not recommended. [y/n] (n): n

How many aliases do you want to generate? (5): 200
At the safe default pace (5/hour, 15/day), generating 200 alias(es) will
take about 14 day(s) (~13d 0h). The script keeps running until they're
all generated — it does not stop early.

Maximum aliases per calendar day? (15): 15
Spread the run over how many hours? (313.0): 313

╭─────────────────── Accounts (accounts.json) ───────────────────╮
│   [a]    all accounts      run the 5 account(s) below in parallel │
│   [1]    main              cookies/cookie.txt                   │
│   [2]    iCloud2           cookies/secondary.txt                │
│   [3]    iCloud3           cookies/third.txt                    │
│   [4]    iCloud4           cookies/fourth.txt                   │
│   [5]    iCloud5           cookies/fifth.txt                    │
│   [0]    default cookie    cookies/cookie.txt                   │
╰─────────────────────────────────────────────────────────────────╯
Which account(s)? Numbers or names, comma-separated — e.g. "1,2,4" (all): 1,2,4,5
Selected 4/5 account(s): main, iCloud2, iCloud4, iCloud5

╭──────────────────── Review ─────────────────────╮
│         Aliases    200                           │
│    Max per hour    5/hour                        │
│     Daily limit    15/day                        │
│        Duration    313 h (~14 day(s))            │
│            Pace    ~0.6/hour                     │
│        Override    off (safe defaults)           │
│   Accounts file    accounts.json                 │
│      Account(s)    main, iCloud2, iCloud4, iCloud5 │
╰───────────────────────────────────────────────────╯
Proceed? [y/n] (y): y
```

Que veulent dire les questions ?

| Question | Signification |
|---|---|
| **Override the safe limits…** | Active volontairement le mode risqué (voir ci-dessous). Par défaut : non. |
| **How many aliases…** | Combien d'alias tu veux créer **au total** — pas de plafond ; l'outil calcule et affiche tout de suite combien de temps ça prendra pour rester safe |
| **Maximum… per calendar day** | Plafond d'alias par jour calendaire (15 par défaut, en sécurité) |
| **Spread the run over how many hours** | Sur combien d'heures étaler la génération (pré-rempli avec la durée sûre calculée juste au-dessus) |
| **Which account(s)?** | Quels comptes utiliser, si un `accounts.json` existe : `all` (défaut) pour tous, des numéros ou noms séparés par des virgules pour un sous-ensemble (ex. `1,2,4` ou `main,iCloud4`), un seul numéro pour un seul compte, ou `0` pour le cookie par défaut |

> ✅ **Le script ne s'arrête jamais avant d'avoir généré le nombre demandé.** Si tu demandes 200 alias, il tourne le temps qu'il faut (plusieurs jours si besoin) en respectant 5/heure et 15/jour — il ne s'arrête pas à 15 puis abandonne. Il faut juste **laisser le terminal ouvert** pendant toute la durée (voir plus bas pour lancer ça en arrière-plan).

Avant de démarrer, l'outil te dit aussi combien d'alias tu as **déjà générés aujourd'hui** (lu depuis l'historique local `generation_log.jsonl`, cumulé même sur plusieurs lancements dans la même journée) :

```text
[00:38:56] 3 alias(es) already generated today (calendar day, limit 15/day).
[00:38:56] Generating 200 alias(es) over ~13d 0h (~14 day(s)) (max 5/hour, 15/day).
```

Ensuite, un **compte à rebours en direct** s'affiche entre chaque alias, avec le nombre d'alias **restants** et ton compteur du jour qui progresse en direct :

```text
⠹ Alias 1/200 (200 remaining) — 0/15 today — next at 01:25:43 in 46m 47s
```

> ⏳ **Laisse la fenêtre ouverte** pendant toute la durée du run : étaler les alias dans le temps est exactement ce qui protège ton compte. Pour un run de plusieurs jours, pense à lancer ça sur une machine qui reste allumée (ou dans un `tmux`/`screen`/service en arrière-plan).

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

En mode override, la durée proposée correspond **exactement au rythme demandé** : `count / max-per-hour`. Exemple : 25 alias à 5/heure → durée suggérée de **5 h**, et le run se termine bien dans cette fenêtre (pas de rallongement automatique au rythme « confortable » de 4/heure utilisé hors override). L'historique du jour est aussi ignoré dans le calcul, comme pendant la génération. La durée n'est rallongée que si elle est mathématiquement impossible (ex. 50 alias avec un plafond de 25/jour ne tiennent pas en 10 h).

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
| `--account` | Restreint le run à certains comptes du fichier (répétable ou séparés par des virgules : `--account "main,iCloud2"`) |

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

# Générer pour un sous-ensemble de comptes seulement (ex. 4 comptes sur 5) :
# répète --account, ou passe une liste séparée par des virgules
python3 cli.py generate --count 15 --account "main,iCloud2,iCloud4,iCloud5"
python3 cli.py generate --count 15 --account main --account iCloud2

# Lister sur tous les comptes, avec export
python3 cli.py list --accounts-file accounts.json --export tous_les_comptes.csv

# Lister seulement certains comptes
python3 cli.py list --account "iCloud2,iCloud3"
```

> 💡 Dans le **menu interactif**, plus besoin de flags : dès qu'un `accounts.json` existe, un tableau des comptes s'affiche et tu tapes simplement les numéros voulus (ex. `1,2,4,5` pour 4 comptes sur 5), `all` pour tous, ou `0` pour le cookie par défaut.

Pendant la génération multi-comptes, un **tableau de bord en direct** affiche une ligne par compte avec son propre compte à rebours :

```text
(main)       Alias 2/10 (8 remaining) — next at 01:12:04 in 12m 3s
(secondary)  Alias 1/5 (5 remaining) — next at 01:05:30 in 5m 29s
```

---

## 🚫 Détecter, désactiver & supprimer les alias bannis Amazon

Quand Amazon suspend un compte lié à un de tes alias, il envoie un mail de suspension
(objet localisé du type « your amazon account is suspended » / « votre compte amazon a
été suspendu ») contenant un lien d'appel **`baa-customer-appeal`**. L'alias, lui, reste
actif et continue de rediriger. Cette fonction repère ces alias « bannis » et te propose
de les désactiver (et éventuellement de les supprimer).

**Deux signaux de ban (« modes ») :**

| Mode | Ce qu'il cherche dans Gmail | Action par défaut |
| --- | --- | --- |
| **`appeal`** | le **texte** `baa-customer-appeal` (compte banni) | **désactiver** |
| **`on-hold`** | l'**objet** « Sign in to resolve: Your Amazon account is temporarily on hold » | **désactiver + supprimer** |
| **`all`** | les deux à la fois | chacun garde son action |

Tu choisis un mode ou les deux. Quand les deux tournent ensemble, chaque alias reçoit
l'action de **son** signal (un alias repéré par les deux est **supprimé**, l'action la plus
forte l'emporte).

**Comment ça marche :**

1. Le script se connecte en **IMAP à ta/tes boîte(s) Gmail** (celles vers lesquelles tes
   alias redirigent — voir le multi-comptes plus bas) et cherche, pour chaque mode, les
   mails correspondants. Pour `appeal` c'est le marqueur `baa-customer-appeal` (présent
   dans chaque mail de suspension, qu'Amazon relaie via iCloud avec un expéditeur du type
   `baa-customer-appeal_at_amazon_ca_…@icloud.com`) — une ancre fiable et indépendante de
   la langue, contrairement à l'objet qui est localisé. Pour `on-hold` c'est l'objet du
   mail « …temporarily on hold ». La boîte est ouverte **en lecture seule** (`BODY.PEEK`) :
   rien n'est marqué lu ni modifié.
2. Il t'affiche la **liste des alias** qui ont reçu ces mails, avec l'action prévue.
3. Il croise cette liste avec les alias de **chaque compte iCloud** et t'annonce, compte
   par compte, quels alias sont bannis (« compte iCloud X → tels alias »).
4. Avant toute action, il **vérifie que tes cookies permettent bien de désactiver** (sonde
   non destructive — il ne touche à aucun alias réel).
5. Il te **demande confirmation** par compte, puis :
   - **désactivation** : désactive les alias bannis encore actifs. C'est **réversible**
     côté iCloud (réactivable).
   - **désactivation + suppression** : désactive puis **supprime définitivement** l'alias.
     iCloud n'autorise la suppression que d'un alias désactivé, donc l'ordre désactiver →
     supprimer est fait automatiquement. ⚠️ **Irréversible.** Le mode `on-hold` fait ça par
     défaut ; pour `appeal`, ajoute le drapeau `--delete` (ou le prompt du menu).
     L'authentification reste la même (tes cookies).

**Configuration (une seule fois) — le(s) mot(s) de passe d'application Gmail :**

```bash
# copie le modèle puis remplis tes infos (ce fichier n'est jamais poussé sur git)
cp banscan.example.json banscan.json
```

**Une seule boîte Gmail :**

```json
{
  "address": "toncompte@gmail.com",
  "app_password": "abcd efgh ijkl mnop",
  "imap_host": "imap.gmail.com",
  "imap_port": 993,
  "text_query": "baa-customer-appeal",
  "subject_query": ""
}
```

**Plusieurs boîtes Gmail (multi-comptes)** — sur le même principe que le `accounts.json`
des comptes iCloud, liste tes boîtes sous `accounts` et elles seront **toutes scannées**
(les alias trouvés sont fusionnés puis croisés avec tous tes comptes iCloud) :

```json
{
  "imap_host": "imap.gmail.com",
  "imap_port": 993,
  "accounts": [
    { "name": "gmail1", "address": "compte1@gmail.com", "app_password": "abcd efgh ijkl mnop" },
    { "name": "gmail2", "address": "compte2@gmail.com", "app_password": "qrst uvwx yzab cdef" }
  ],
  "text_query": "baa-customer-appeal",
  "subject_query": ""
}
```

> 🔎 En pratique, seuls `address` et `app_password` (par boîte) te concernent. `imap_host`
> / `imap_port` sont communs (surchargeables par boîte), `name` est facultatif (par défaut
> l'adresse). Le mode `appeal` cherche le texte **`baa-customer-appeal`** (Amazon relaie
> via iCloud, donc filtrer sur l'expéditeur « amazon » ne marche pas et n'est
> volontairement pas fait) ; le mode `on-hold` cherche l'objet « …temporarily on hold ».
> `text_query` / `subject_query` restent, pour rétro-compatibilité, les réglages du mode
> `appeal` ; un objet `signals` optionnel permet d'ajuster finement chaque mode
> (`{"signals": {"on-hold": {"subject_query": "…"}}}`).

> 🔑 **`app_password`** n'est **pas** ton mot de passe Gmail habituel : c'est un
> **mot de passe d'application** (Compte Google → Sécurité → Validation en 2 étapes →
> Mots de passe des applications). L'accès IMAP doit aussi être activé dans les
> paramètres Gmail. Tu peux aussi passer par les variables d'environnement
> `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD`, ou laisser le script te les demander au premier
> lancement (le mot de passe n'est jamais affiché).

**Utilisation :**

Dans le **menu interactif**, choisis **`3`** (Ban check). Il te demande d'abord **quel(s)
signal(aux)** chercher (`appeal`, `on-hold`, ou `all`), puis démarre par défaut en **mode
simulation** (dry-run). Pour le signal `appeal`, il propose aussi de supprimer (en plus de
désactiver) ; le signal `on-hold` supprime déjà par défaut. En dry-run, il te propose
d'**exporter la liste des alias signalés** (ceux théoriquement à traiter) vers un fichier
**`.txt`** (un alias par ligne) ou **`.csv`** (colonnes Compte, Label, Alias, État).

En ligne de commande (le mode par défaut est `appeal`) :

```bash
# scan + rapport uniquement (aucune action), sur tous les comptes du accounts.json
python3 cli.py bancheck --dry-run

# chercher le signal « compte on hold » (désactive + supprime par défaut)
python3 cli.py bancheck --mode on-hold --dry-run

# chercher les deux signaux en une passe (appeal → désactive, on-hold → désactive+supprime)
python3 cli.py bancheck --mode all --dry-run

# dry-run + export de la liste des alias signalés (format déduit de l'extension)
python3 cli.py bancheck --dry-run --export alias_bannis.csv
python3 cli.py bancheck --dry-run --export alias_bannis.txt
# forcer le format quel que soit le nom de fichier
python3 cli.py bancheck --dry-run --export alias_bannis.dat --export-format csv

# scan puis DÉSACTIVATION (réversible), avec une confirmation par compte
python3 cli.py bancheck

# scan puis DÉSACTIVATION + SUPPRESSION définitive (irréversible), confirmation par compte
# (--delete force la suppression sur TOUS les modes sélectionnés, y compris appeal)
python3 cli.py bancheck --delete
python3 cli.py bancheck --mode all --delete

# limiter à certains comptes
python3 cli.py bancheck --account "iCloud2,iCloud3"

# agir sans confirmation par compte (à utiliser en connaissance de cause)
python3 cli.py bancheck --yes
python3 cli.py bancheck --mode all --yes
```

> 📄 **`--export`** liste les alias qui *seraient* traités : ceux à désactiver ne comptent
> que s'ils sont encore actifs, ceux à supprimer comptent toujours (les inactifs sont
> supprimés directement). La liste est établie à partir du croisement Gmail ↔ comptes
> iCloud, donc elle est complète même si les cookies d'un compte sont périmés.

> ⚠️ Si un compte affiche « Impossible d'agir avec ces cookies », c'est que sa session
> iCloud est périmée : réexporte des cookies frais (voir
> [Récupérer ton cookie iCloud](#-récupérer-ton-cookie-icloud)) puis relance.

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

**J'ai demandé 200 alias, pourquoi ça n'en génère que 15 ?**
Ça ne devrait plus arriver — si tu vois ça, ta version est à jour et c'est un bug, remonte-le. Le comportement normal : demander 200 alias calcule automatiquement la durée sûre nécessaire (~14 jours à 15/jour) et **le script tourne tout ce temps sans s'arrêter**, jusqu'à avoir généré les 200. Rien n'est jamais tronqué au plafond journalier — le plafond ne fait qu'étaler la génération sur plus de jours.

**Le compteur « alias déjà générés aujourd'hui », c'est pour quoi ?**
Il est **informatif** (et alimente le compte à rebours en direct) : il te dit combien ce compte a déjà généré aujourd'hui, y compris via un lancement précédent dans la même journée. Il n'annule ni ne réduit jamais le nombre total que tu as demandé.

**J'ai plus d'adresses dans Réglages > iCloud sur mon iPhone que dans l'export de l'outil**
C'est normal, et ce n'est pas un bug de fetch : chaque `list`/export affiche désormais le total exact renvoyé par Apple (`Apple returned N alias(es) total...`), et ce total est complet — vérifié, aucune pagination côté serveur. L'écart vient d'ailleurs : l'écran iPhone **Réglages > [ton nom] > iCloud > Masquer mon adresse e-mail** regroupe aussi les adresses créées automatiquement via **« Se connecter avec Apple »** (une par appli où tu l'as utilisé). Ce sont des alias qui viennent d'un système Apple différent (`appleid.apple.com`, pas `icloud.com`) et que cet outil ne gère pas — reconnaissables sur iPhone à leur libellé du style *« Utilisé avec [nom de l'appli] »*.

---

## 🧰 Annexe : tout installer de zéro (macOS & Windows)

> Cette annexe est pour toi si tu n'as **jamais lancé de script** sur ta machine.
> On part de zéro : ouvrir un terminal, installer Python, récupérer le projet,
> installer les dépendances, lancer l'outil. Compte **10–15 minutes**.

### 💡 C'est quoi tout ça, d'abord ?

| Mot | En clair |
|---|---|
| **Terminal** | Une fenêtre où tu tapes des commandes au clavier au lieu de cliquer. C'est là-dedans que tu lanceras l'outil. |
| **Python** | Le langage dans lequel le script est écrit. Il faut l'installer une fois pour que ta machine sache l'exécuter. |
| **pip** | Le « magasin d'applications » de Python : il télécharge les briques dont le script a besoin. Il est installé automatiquement avec Python. |
| **Dépendances** | Les briques en question (`aiohttp`, `rich`, `click`, `certifi`, `cryptography`). Tu n'as **pas** à les connaître : une seule commande les installe toutes. |
| **git** | L'outil qui télécharge le projet et permet de le mettre à jour plus tard. (Facultatif : tu peux aussi télécharger un ZIP.) |

Dans tout ce qui suit : tape (ou colle) la commande dans le terminal, puis appuie sur **Entrée**. Une commande qui ne renvoie rien, c'est souvent bon signe.

---

### 🍎 Sur macOS

**1. Ouvrir le Terminal**

Appuie sur `⌘ + Espace` (Spotlight), tape `Terminal`, puis **Entrée**. Une fenêtre blanche ou noire s'ouvre avec un curseur qui clignote : c'est là que tout se passe.

**2. Installer Python**

macOS n'inclut pas de Python assez récent. Installe-le depuis le site officiel :

1. Va sur **[python.org/downloads](https://www.python.org/downloads/)** et clique le gros bouton jaune **Download Python 3.x** (il faut **3.12 ou plus**).
2. Ouvre le fichier `.pkg` téléchargé et laisse-toi guider (Continuer → Continuer → Installer).
3. À la fin, l'installeur ouvre un dossier avec un fichier **`Install Certificates.command`** : **double-clique dessus** (il installe les certificats HTTPS — sans ça, la connexion à iCloud peut échouer avec une erreur SSL).

Vérifie ensuite dans le Terminal :

```bash
python3 --version
```

Tu dois voir quelque chose comme `Python 3.13.x`. ✅ (pip est inclus, rien de plus à installer.)

**3. Installer git (pour télécharger le projet)**

```bash
git --version
```

- Si un numéro de version s'affiche : git est déjà là, passe à l'étape suivante.
- Sinon, macOS te propose tout seul d'installer les **outils en ligne de commande** : clique **Installer** dans la fenêtre qui apparaît, attends la fin, puis relance `git --version`.

**4. Télécharger le projet et installer les dépendances**

```bash
cd ~/Desktop
git clone https://github.com/usedev00-spec/mail-gen
cd mail-gen
python3 -m pip install -r requirements.txt
```

Ces 4 commandes : se placer sur le Bureau → télécharger le projet dans un dossier `mail-gen` → entrer dans ce dossier → installer d'un coup toutes les dépendances (des lignes défilent, c'est normal ; ça se termine par `Successfully installed …`).

**5. Lancer l'outil**

```bash
python3 cli.py
```

Le menu interactif s'affiche 🎉. Reprends ensuite le guide au chapitre [Activer ta clé d'accès](#-activer-ta-clé-daccès).

> 💡 **Pour les prochaines fois** : rouvre le Terminal, tape `cd ~/Desktop/mail-gen` puis `python3 cli.py`. C'est tout.

---

### 🪟 Sur Windows

**1. Installer Python**

1. Va sur **[python.org/downloads](https://www.python.org/downloads/)** et clique **Download Python 3.x** (il faut **3.12 ou plus**).
2. Lance le fichier `.exe` téléchargé.
3. ⚠️ **Étape la plus importante de toute la page** : sur le premier écran de l'installeur, **coche la case « Add python.exe to PATH »** en bas, **avant** de cliquer « Install Now ». Si tu l'oublies, Windows ne trouvera pas la commande `python` (c'est l'erreur n°1 des débutants — la solution est plus bas dans le dépannage).
4. Clique **Install Now** et laisse finir.

**2. Ouvrir un terminal**

Clique sur le menu **Démarrer**, tape `PowerShell`, puis **Entrée**. Une fenêtre bleue ou noire s'ouvre : c'est ton terminal.

Vérifie l'installation :

```powershell
python --version
```

Tu dois voir `Python 3.13.x` (ou similaire). ✅ (pip est inclus.)

> Sur Windows la commande s'appelle **`python`** (sans le `3`). Partout où le guide écrit `python3 cli.py ...`, tape `python cli.py ...`.

**3. Télécharger le projet**

Deux options — choisis la plus simple pour toi :

- **Option A, sans rien installer (ZIP)** : sur la page GitHub du projet, clique le bouton vert **Code → Download ZIP**. Ouvre le ZIP téléchargé et **extrais** le dossier sur ton Bureau (clic droit → *Extraire tout…*). Tu obtiens un dossier `mail-gen` (parfois `mail-gen-main` — les commandes ci-dessous marchent pareil, adapte juste le nom).
- **Option B, avec git (permet `git pull` pour les mises à jour)** : installe **[Git pour Windows](https://git-scm.com/download/win)** (laisse toutes les options par défaut, « Suivant » partout), ferme puis rouvre PowerShell, puis :

  ```powershell
  cd $HOME\Desktop
  git clone https://github.com/usedev00-spec/mail-gen
  ```

**4. Installer les dépendances**

Dans PowerShell :

```powershell
cd $HOME\Desktop\mail-gen
python -m pip install -r requirements.txt
```

Des lignes défilent puis ça se termine par `Successfully installed …` : toutes les briques (`aiohttp`, `rich`, `click`, `certifi`, `cryptography`) sont en place.

**5. Lancer l'outil**

```powershell
python cli.py
```

Le menu interactif s'affiche 🎉. Reprends ensuite le guide au chapitre [Activer ta clé d'accès](#-activer-ta-clé-daccès).

> 💡 **Pour les prochaines fois** : rouvre PowerShell, tape `cd $HOME\Desktop\mail-gen` puis `python cli.py`. C'est tout.

---

### 🚑 Dépannage installation (les 6 erreurs classiques)

**« `python` n'est pas reconnu… » (Windows)**
Tu as oublié de cocher **« Add python.exe to PATH »** à l'installation. Le plus simple : relance l'installeur Python téléchargé, choisis **Modify** → coche l'option PATH (ou désinstalle/réinstalle en cochant la case), puis **ferme et rouvre PowerShell**. En attendant, la commande `py` marche souvent : `py cli.py`.

**Windows ouvre le Microsoft Store quand je tape `python`**
C'est un faux `python` fourni par Windows. Soit installe Python depuis le Store (ça marche aussi), soit désactive l'alias : Paramètres → Applications → Paramètres avancés des applications → **Alias d'exécution d'applications** → désactive les deux entrées « python », puis rouvre PowerShell.

**« `command not found: python3` » (macOS)**
Python n'est pas (ou mal) installé : refais l'étape 2 macOS avec l'installeur de python.org, puis **ferme et rouvre le Terminal**.

**« `pip` n'est pas reconnu » / « No module named pip »**
N'appelle jamais `pip` tout seul : utilise toujours la forme longue, qui marche partout — `python3 -m pip install -r requirements.txt` (macOS) ou `python -m pip install -r requirements.txt` (Windows).

**« No such file or directory: cli.py » / « can't open file 'cli.py' »**
Tu n'es pas **dans le dossier du projet**. Tape `cd ~/Desktop/mail-gen` (macOS) ou `cd $HOME\Desktop\mail-gen` (Windows) puis relance. Astuce : `ls` (macOS) ou `dir` (Windows) liste les fichiers du dossier où tu te trouves — tu dois y voir `cli.py`.

**Erreur `SSL: CERTIFICATE_VERIFY_FAILED` (macOS)**
Tu as sauté le double-clic sur **`Install Certificates.command`** (fin de l'étape 2 macOS). Il est dans `Applications → Python 3.x` : double-clique-le et relance l'outil.

---

## 📄 Licence

Sous licence MIT — voir le fichier [LICENSE](./LICENSE).
