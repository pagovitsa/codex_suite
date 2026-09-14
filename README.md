# Codex Suite — HTTP API

Το πραγματικό Codex CLI (`codex app-server`) πίσω από το HTTP API του
[Codex Broker](https://github.com/jonasjancarik/codex-broker).
Παρέχει prompts, streaming, εργασίες σε project, sessions, κατάσταση και interrupt.
Το HTTPS το αναλαμβάνει ο δικός σου reverse proxy.

## Πού τρέχει

Το ίδιο πακέτο χρησιμοποιεί **Linux containers**:

- Linux με Docker Engine και Docker Compose.
- Windows με Docker Desktop σε λειτουργία Linux containers και λειτουργικό WSL 2 / virtualization.
- macOS με Docker Desktop.

Το build υποστηρίζει `amd64` και `arm64`. Δεν είναι image για Windows containers.
Ο host πρέπει να επιτρέπει τα Linux user namespaces που χρειάζεται το sandbox.
Σε Linux hosts με AppArmor χρειάζεται το πρόσθετο βήμα παρακάτω.
Συστήματα με πρόσθετους περιορισμούς, όπως Enhanced Container Isolation ή
απενεργοποιημένα unprivileged user namespaces, χρειάζονται επιπλέον έλεγχο συμβατότητας.

## Εκκίνηση — ίδιες εντολές σε PowerShell και Linux shell

Άνοιξε terminal μέσα στον φάκελο αυτού του README. Απαιτείται Docker με Compose·
δεν χρειάζεται Python ή Node στον host.

```shell
docker info --format '{{.OSType}}'
docker info --format '{{json .SecurityOptions}}'
```

Η πρώτη εντολή πρέπει να δείξει `linux`. Αν η δεύτερη περιλαμβάνει `apparmor`,
ακολούθησε πρώτα την ενότητα AppArmor.

```shell
docker compose run --rm --build init
docker compose up -d --build --wait --wait-timeout 180 codex-broker
docker compose run --rm client check
```

Το `init` δημιουργεί τρία διαφορετικά τυχαία κλειδιά και τα bindings τους στον
φάκελο `secrets`. Επαναλαμβάνεται χωρίς αλλαγή κλειδιών. Αν βρει ασυμφωνία με
υπάρχοντα αρχεία, σταματά για να μη χαλάσει την υπάρχουσα πρόσβαση.

Το API ακούει στο **http://127.0.0.1:3400**. Το readiness ελέγχει και το πραγματικό
sandbox πριν επιτρέψει εργασίες. Το `client check` ελέγχει readiness, έγκυρη
πρόσβαση στο OpenAPI και απόρριψη ανώνυμων/λανθασμένων κλειδιών, χωρίς κλήση μοντέλου.

Πρώτο build: κατεβάζει το βασικό image, το pinned Codex CLI και εργαλεία
Python, Git, ripgrep, Node.js/npm. Για project με άλλες εξαρτήσεις, προσάρμοσε το Dockerfile.

## Login στο Codex

Για ChatGPT login:

```shell
docker compose run --rm client login
```

Άνοιξε το `loginUrl` που εμφανίζεται και βάλε το `userCode` στον browser σου.
Αν δεν εμφανιστούν αμέσως, το `status` δείχνει την ενότητα `deviceAuth`:

```shell
docker compose run --rm client status
docker compose run --rm client models
```

Περίμενε `state: authenticated`. Το device login πρέπει να είναι διαθέσιμο στον
λογαριασμό/workspace σου. Εναλλακτικά, για OpenAI API key:

```shell
docker compose run --rm client api-key
```

Το κλειδί ζητείται χωρίς εμφάνιση στην οθόνη. Τα upstream credentials αποθηκεύονται
στο Docker volume `/data`. Δεν χρειάζεται αντιγραφή των credentials του Codex app.
Η επιλογή login καθορίζει πώς χρησιμοποιείται ο λογαριασμός σου· δες την
[επίσημη τεκμηρίωση authentication](https://developers.openai.com/codex/auth).

## Prompt και απάντηση

Διάλεξε πραγματικό model id από το `models` και αντικατάστησε το `MODEL_ID`:

```shell
docker compose run --rm client chat --model MODEL_ID "Explain what this project does."
docker compose run --rm client chat --model MODEL_ID --stream "Summarize the project."
```

Αυτό χρησιμοποιεί το `secrets/chat.key` με read-only profile. Το default μοντέλο
για native tasks το επιλέγει το Codex· δεν έχει επιβληθεί συγκεκριμένο μοντέλο.

Για απευθείας χρήση με OpenAI-compatible client:

| Ρύθμιση | Τιμή |
| --- | --- |
| Base URL | `http://127.0.0.1:3400/v1` ή το δικό σου HTTPS URL με `/v1` |
| API key για chat | Περιεχόμενο του `secrets/chat.key` |
| API key για αλλαγές project | Περιεχόμενο του `secrets/agent.key` |
| Model | Ένα id από `GET /v1/models` |

Παράδειγμα HTTP body για `POST /v1/responses`:

```json
{"model":"MODEL_ID","input":"Explain this project.","stream":false}
```

Headers: `Authorization: Bearer <chat.key>` και `Content-Type: application/json`.
Υποστηρίζεται επίσης `POST /v1/chat/completions` και SSE streaming.
Η συμβατότητα καλύπτει συγκεκριμένο υποσύνολο του OpenAI API: π.χ. caller-defined
`tools` και sampling parameters απορρίπτονται. Δεν είναι γενικό OpenAI proxy.

## Εργασίες που αλλάζουν αρχεία

Βάλε το project σου στον φάκελο `workspace`, ή αντέγραψε το `.env.example` σε
`.env` και όρισε `PROJECT_PATH` στον υπάρχοντα φάκελο που θέλεις:

```dotenv
# Windows παράδειγμα — forward slashes, χωρίς εισαγωγικά
PROJECT_PATH=C:/Projects/my-project
```

Σε Linux μπορεί να είναι `/home/your-user/projects/my-project`.
Το container το βλέπει πάντα ως `/workspaces/project`. Το runtime τρέχει με
UID/GID 1000. Σε Linux ο επιλεγμένος φάκελος πρέπει να είναι εγγράψιμος από αυτόν
τον χρήστη· μην κάνεις μαζικό chmod/chown σε άλλους φακέλους.
Οι αλλαγές γίνονται απευθείας στα αρχεία του project.

Μετά από αλλαγή του `.env`:

```shell
docker compose up -d --force-recreate --wait codex-broker
docker compose run --rm client task "Create hello.py that prints hello, run it, and report the result."
```

Η απάντηση περιέχει `threadId` και `turnId`. Αντικατάστησε τα `THREAD_ID`, `TURN_ID`:

```shell
docker compose run --rm client turn THREAD_ID TURN_ID
docker compose run --rm client events THREAD_ID TURN_ID
docker compose run --rm client task --thread THREAD_ID "Add a short README for hello.py."
docker compose run --rm client interrupt THREAD_ID TURN_ID
```

Για την ίδια δυνατότητα μέσω του compatible API, χρησιμοποίησε `agent.key`
ή πρόσθεσε `--agent` στο `client chat`. Το native API δίνει πιο άμεσο έλεγχο
σε sessions, turns, events και interrupt.

Native requests χρησιμοποιούν το `secrets/internal.key` και owner `local`:

1. `POST /v1/owners/local/threads` με
   `{"threadId":"my-task","configProfile":"agent","cwd":"/workspaces/project"}`.
2. `POST /v1/owners/local/threads/my-task/turns` με
   `{"input":[{"type":"text","text":"Fix the bug and run tests."}],"mode":"queue"}`.
3. `GET /v1/owners/local/threads/my-task/turns/<turnId>` για κατάσταση.
4. `GET /v1/owners/local/threads/my-task/events?turnId=<turnId>&after=0` για SSE.
5. `POST /v1/owners/local/threads/my-task/turns/<turnId>/interrupt` με `{}` για διακοπή.

Το πλήρες schema είναι στο `GET /openapi.json` με το internal key.
Το internal key έχει διαχειριστική πρόσβαση, περιλαμβανομένων των login endpoints.
Κράτησέ το για δικά σου trusted scripts/backend. Τα chat/agent keys είναι για clients.

## Το δικό σου HTTPS proxy

Proxy στο ίδιο host: upstream `http://127.0.0.1:3400`.
Proxy σε άλλο container: σύνδεσέ το στο Docker network `codex-suite_default`
και χρησιμοποίησε upstream `http://codex-broker:3400`.
Proxy σε άλλο μηχάνημα: βάλε στο `.env` το συγκεκριμένο LAN IP στο `BIND_ADDRESS`,
κάνε recreate και επέτρεψε τη θύρα 3400 μόνο από το proxy στο firewall.

Πέρασε το `Authorization` header αυτούσιο, διατήρησε τα paths χωρίς αφαίρεση του
`/v1`, απενεργοποίησε το buffering/caching για SSE και δώσε timeout τουλάχιστον
30 λεπτών για μεγάλα turns. Το suite χρησιμοποιεί όριο 30 λεπτών ανά turn,
ρυθμιζόμενο στο Compose. Χρειάζεται HTTP/SSE, όχι WebSocket forwarding.

## Linux hosts με AppArmor

Το seccomp JSON διαβάζεται από το Compose απευθείας από το πακέτο. Δεν χρειάζεται
αντιγραφή του seccomp μέσα στη VM του Docker Desktop.
Το AppArmor, όταν υπάρχει, είναι host policy και πρέπει να εγκατασταθεί στον
Linux host του Docker daemon:

```shell
sh broker/scripts/install-host-security-profiles.sh --dry-run
sudo sh broker/scripts/install-host-security-profiles.sh
sudo sh broker/scripts/install-host-security-profiles.sh --check
docker compose -f compose.yaml -f compose.apparmor.yaml up -d --build --wait codex-broker
```

Χρησιμοποίησε και τα δύο `-f` σε επόμενα `up`/recreate στον ίδιο host.
Η εγκατάσταση του profile απαιτεί τα εργαλεία AppArmor της διανομής όταν είναι ενεργό.
Σε Docker Desktop που δεν αναφέρει AppArmor, χρησιμοποίησε μόνο το βασικό Compose.
Το suite δεν απενεργοποιεί το sandbox για να παρακάμψει αποτυχημένο preflight.

## Διαχείριση και backup

```shell
docker compose logs --tail 100 codex-broker
docker compose ps
docker compose down
```

Το `down` διατηρεί login, sessions και ιστορικό στο named volume
`codex-suite_broker-data`. Το `down -v` τα διαγράφει· μην το χρησιμοποιείς για restart.
Για μεταφορά σε άλλο PC κράτησε τον φάκελο suite, τα `secrets`, το project και
backup του named volume αφού σταματήσεις τον broker. Τα secrets και τα backups
του volume περιέχουν πρόσβαση στον λογαριασμό σου.

## Κατάσταση ελέγχων σε αυτό το PC

Στις 2026-09-14 ολοκληρώθηκαν πραγματικό Docker build, εκκίνηση και sandbox
preflight σε Windows 11 με Docker Desktop / WSL 2. Το HTTP API και οι έλεγχοι
authentication πέρασαν τόσο από τα Windows όσο και από το client container.
Το ChatGPT login ολοκληρώθηκε. Πραγματικό prompt επέστρεψε `CODEX_SUITE_OK`,
το SSE streaming ολοκληρώθηκε και native task δημιούργησε/εκτέλεσε `hello.py`
με έξοδο `Hello from Docker Codex Suite`. Login, συνεδρία και ιστορικό
διατηρήθηκαν μετά από recreate και restart του container.
Δες το `VERIFICATION.md` για αναλυτικά αποτελέσματα.

Το τοπικό demo χρησιμοποιεί το Compose project **`codex-suite-demo`**, το volume
`codex-suite-demo_broker-data` και το network `codex-suite-demo_default`.
Το τοπικό `.env` επιλέγει αυτό το project και δεν περιλαμβάνεται στο ZIP.
Ο φάκελος `workspace` είναι ο αποκλειστικός φάκελος δοκιμών για αλλαγές αρχείων.

Σε αυτό το PC το Docker είναι στο `D:\DockerDesktop`. Αν το `docker` δεν βρίσκεται
στο PATH, άνοιξε PowerShell μέσα στον φάκελο αυτού του README και εκτέλεσε:

```powershell
$env:PATH = 'D:/DockerDesktop/resources/bin;' + $env:PATH
docker compose ps
docker compose run --rm client status
docker compose up -d --wait codex-broker
```

Το API είναι στο `http://127.0.0.1:3400`, με readiness στο `/readyz`.
Για proxy σε container αυτού του demo χρησιμοποίησε το `codex-suite-demo_default`.

Σε άλλο Windows PC που δεν έχει ακόμη προετοιμαστεί, ξεκίνα από PowerShell
**ως διαχειριστής**:

```powershell
wsl --install --no-distribution
```

Ακολούθησε τυχόν απαίτηση επανεκκίνησης. Αν παραμείνει το μήνυμα virtualization,
έλεγξε τη ρύθμιση Intel VT-x/Virtualization στο BIOS/UEFI και τη διαθεσιμότητα
του Windows hypervisor. Κατόπιν άνοιξε το
[Docker Desktop για Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
σε Linux containers (εγκατάστησέ το μόνο αν λείπει) και εκτέλεσε τις εντολές εκκίνησης παραπάνω.

## Προέλευση

Το `broker/` περιλαμβάνει τα απαιτούμενα source files από Codex Broker commit
`0517227a874ec410c75b2eb5577ed3711dff7231` (package version `0.10.3`),
με Codex CLI `0.153.4` όπως το ορίζει το upstream Dockerfile.
Τα line endings κανονικοποιήθηκαν σε LF για Linux. Το root Dockerfile προσθέτει
Git/ripgrep/Node.js/npm και τα scripts του suite, και εγκαθιστά μαζί τα
`codex` / `codex-code-mode-host` στο `/usr/local/bin` ώστε να λειτουργούν τα tools.
Το source του broker δεν άλλαξε
λογική. Ο κώδικας του upstream είχε ανακτηθεί στις 2026-09-14.
Το βασικό Python image και τα πακέτα του OS επιλύονται στο build· δεν πρόκειται
για byte-for-byte αναπαραγώγιμο image.

Πηγές: [Codex Broker στο συγκεκριμένο commit](https://github.com/jonasjancarik/codex-broker/tree/0517227a874ec410c75b2eb5577ed3711dff7231),
[Docker Compose seccomp loading](https://github.com/docker/compose/blob/main/pkg/compose/create.go),
[Codex authentication](https://developers.openai.com/codex/auth).
