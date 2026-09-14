# Έλεγχοι — 2026-09-14

**Το τοπικό Docker demo τρέχει και δοκιμάστηκε με πραγματικό ChatGPT login,
απάντηση μοντέλου, SSE streaming, δημιουργία/εκτέλεση αρχείου και restart.**

Οι έλεγχοι έγιναν σε Windows 11 Pro, build 26200, με Python 3.12.14.
Το Docker Compose v5.5.1 κατέβηκε προσωρινά από το επίσημο GitHub release του Docker
και το SHA-256 του συμφωνούσε με το published asset digest.
Χρησιμοποιήθηκε μόνο ως εργαλείο ελέγχου· δεν εγκαταστάθηκε Docker Engine/Desktop.

| Έλεγχος | Αποτέλεσμα |
| --- | --- |
| Βασικό Compose με όλα τα tool profiles | `config --quiet`: PASS, exit 0 |
| `python test_suite.py` | 5/5 PASS: idempotent init, key/profile bindings, απόρριψη invalid key, διατήρηση τροποποιημένων bindings, redirects, LF entrypoint |
| Upstream `test_openai_compat` πάνω στο vendored source | 26/26 PASS, exit 0 |
| Client σε πραγματικό broker HTTP με fake Codex subprocess | PASS: readiness/auth boundaries, models, sync response, SSE, auth status, task continuation και turn lookup |
| Upstream `test_config_profiles` | 21/22 PASS· μία αποτυχία POSIX file mode σε Windows |
| Επιπλέον sandbox contract / απόρριψη overrides και εκτός-workspace cwd | 2/2 PASS, exit 0 |
| Πέντε επιλεγμένοι native broker έλεγχοι | 3 PASS, 2 ERROR σε Windows teardown |
| Codex release assets | Υπάρχουν τα amd64/arm64 musl archives στο επίσημο `0.153.4` checksum manifest |
| Container build / init | PASS σε Docker Desktop Linux amd64, Codex CLI `0.153.4`, checksum verified |
| Εκκίνηση / πραγματικό sandbox canary | PASS: container Healthy, `/readyz` ready, bubblewrap healthy, `broker-workspace-write` |
| HTTP/auth checks από Windows και από client container | PASS: readiness 200, anonymous/wrong-scope 401, authorized OpenAPI 200 |
| Πραγματικό ChatGPT login | PASS: authenticated, device auth completed με exit 0 |
| Πραγματική απάντηση, `gpt-5.6-luna` | PASS: `/v1/responses` completed, `CODEX_SUITE_OK` |
| Πραγματικό SSE streaming | PASS: text deltas, `STREAM_OK`, `response.completed` |
| Native task και συνέχεια ίδιας συνεδρίας | PASS μετά τη διόρθωση helper binary: `hello.py` δημιουργήθηκε στον host και εκτελέστηκε στο container |
| Recreate και restart | PASS: login διατηρείται, προηγούμενο thread/turn και terminal events ανακτώνται, container Healthy |

Οι upstream API έλεγχοι χρησιμοποιούν το upstream `fake_codex.py`: δοκιμάζουν
broker HTTP, authentication, συμβατότητα, αποθήκευση και streaming. Δεν αποδεικνύουν
μοντέλο, πραγματικά filesystem permissions ή Linux container isolation.

## Οι αποτυχίες παραμένουν καταγεγραμμένες

- Το `test_generated_owner_hash_key_survives_internal_api_key_rotation` αποτυγχάνει
  στο assertion για POSIX mode `0600`: το Windows stat επιστρέφει `0666`.
- Τα `test_device_auth_flow_exposes_login_fields_without_token_material` και
  `test_same_thread_rejects_concurrent_turn` καταλήγουν σε `PermissionError [WinError 32]`
  κατά το cleanup του προσωρινού directory, με ανοικτό SQLite file / process cwd.
  Η ανάγνωση των συγκεκριμένων tests έδειξε ότι δεν κλείνουν όλους τους πόρους
  πριν το `TemporaryDirectory` cleanup. Δεν άλλαξε ο upstream κώδικας και
  δεν παρουσιάζονται αυτοί οι δύο έλεγχοι ως επιτυχείς.
- Οι native έλεγχοι shutdown/interrupt, turn timeout και ξεχωριστού danger-access
  credential ολοκληρώθηκαν επιτυχώς.

## Διόρθωση που προέκυψε από την πραγματική δοκιμή

Η πρώτη απόπειρα native task επέστρεψε completed με μήνυμα ότι δεν μπορούσε
να εκτελέσει tools: έλειπε το `/usr/local/bin/codex-code-mode-host`.
Δεν είχε δημιουργηθεί το ζητούμενο αρχείο, οπότε η απόπειρα δεν θεωρήθηκε επιτυχής.
Το αρχικό upstream Dockerfile αντέγραφε στο runtime path μόνο το `codex`, ενώ
το pinned release περιέχει και το sibling executable `codex-code-mode-host`.
Το root Dockerfile του suite πλέον αντιγράφει και τα δύο μαζί και ελέγχει ότι
ο helper είναι executable. Η λογική Python του vendored broker διατηρείται.

Με νέο build και recreate, η ίδια συνεδρία συνεχίστηκε επιτυχώς:
το πραγματικό μοντέλο δημιούργησε `workspace/hello.py` και εκτέλεσε `python hello.py`.
Το αρχείο ελέγχθηκε στον host και εκτελέστηκε ξανά με `docker exec`, επιστρέφοντας
`Hello from Docker Codex Suite`. Το τελευταίο sandbox preflight μετά το τελικό
restart στις `2026-09-14T12:38:10Z` ήταν Healthy (~0,92s).

## Προετοιμασία και πραγματική εκκίνηση αυτού του host

Ο αρχικός έλεγχος δεν βρήκε το Docker στις συνηθισμένες θέσεις ή στο PATH.
Στη συνέχεια εντοπίστηκε εγκατεστημένο και με ενεργά processes στο `D:\DockerDesktop`.
Το CLI αναφέρει Docker `29.7.2`, με επιλεγμένο context `desktop-linux`.
Οι κλήσεις engine/status δεν ολοκληρώθηκαν. Η απόπειρα `docker desktop restart
--timeout 45` απέτυχε με `Failed to stop Docker Desktop` και `context deadline exceeded`.

Το `wsl --status` ανέφερε ότι δεν μπορεί να ξεκινήσει, και δεν βρέθηκε WSL distribution.
Ακολούθησε έλεγχος με elevation και ενεργοποίηση των απαραίτητων Windows features:

- `VirtualMachinePlatform`: ήταν ήδη `Enabled`.
- `Microsoft-Windows-Subsystem-Linux`: `Disabled` → `Enabled` επιτυχώς.
- Αποτέλεσμα Windows: `restartNeeded: true`, χωρίς σφάλμα.

Έγινε επανεκκίνηση με έγκριση του χρήστη. Μετά το restart το WSL ξεκίνησε.
Το Docker Desktop αρχικά σταμάτησε σε παλιά, μη προσβάσιμα Unix socket files
στους προσωρινούς φακέλους `Docker/run` και `docker-secrets-engine`.
Ελέγχθηκαν οι φάκελοι (περιείχαν μόνο μηδενικού μεγέθους runtime sockets),
το Desktop σταμάτησε με `desktop stop --force`, και οι φάκελοι μετακινήθηκαν
σε γειτονικά backups πριν αναδημιουργηθούν. Δεν έγινε factory reset.
Το Desktop κατόπιν δημιούργησε το `docker-desktop` WSL περιβάλλον και ο engine
απάντησε με Docker `29.7.2`, OS `linux`, seccomp/cgroupns.

Το πραγματικό `compose -p codex-suite-demo run --rm --build init` ολοκληρώθηκε
με exit 0 και διατήρησε τα ήδη δημιουργημένα τοπικά κλειδιά.
Το `up -d --wait --wait-timeout 180 codex-broker` επέστρεψε Healthy, exit 0.
Το sandbox preflight ολοκληρώθηκε στις `2026-09-14T12:32:19Z` σε περίπου 0,9s.
Το `client check` πέρασε από Windows και μέσα από δεύτερο container.
Το ZIP δεν περιέχει κλειδιά, bindings, τοπικό `.env` ή δεδομένα workspace.

## Όρια των ελέγχων

Δεν δοκιμάστηκαν ξεχωριστός Linux host, arm64, API-key authentication
ή το εξωτερικό HTTPS proxy του χρήστη. Το live HTTP chat δοκιμάστηκε μέσω
`/v1/responses`· το `/v1/chat/completions` καλύφθηκε από τα upstream fake-Codex tests.
Το live native interrupt δεν επαναδοκιμάστηκε με μοντέλο· καλύφθηκε από τα
στοχευμένα upstream tests. Οι παλιές αποτυχίες Windows tests παραμένουν παραπάνω.
Η υπηρεσία απαιτεί επιτυχημένο πραγματικό sandbox preflight πριν ξεκινήσει.

## Επανέλεγχος — 2026-09-15

Μετά την αφαίρεση του προαιρετικού host profile, του overlay και του installer,
πέρασαν ξανά τα 5 tests του suite, το `docker compose --profile tools config --quiet`
και το `python client.py check` στο τρέχον demo. Το container παραμένει Healthy.
Δεν χρειάστηκε νέο build ή restart, καθώς το βασικό Compose και το runtime δεν άλλαξαν.

## Source review

Η structural αναζήτηση έγινε με το codebase graph, με πρόσθετη ανάγνωση των
ουσιαστικών source/config files. Το coverage tool ανέφερε metadata changes ακόμη
και μετά το index, οπότε οι τελικές διαπιστώσεις βασίστηκαν και σε άμεση ανάγνωση
και εκτέλεση των ελέγχων. Τα secrets εξαιρέθηκαν από το graph και επαληθεύτηκαν
τοπικά από το init χωρίς εμφάνιση των τιμών. Τα Linux entrypoints κανονικοποιήθηκαν
σε LF· η λογική του vendored broker διατηρήθηκε.
