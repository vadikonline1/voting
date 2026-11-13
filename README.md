# Sistem de Vot (buletin APC)

Sistem de votare online pentru buletinul de vot al Adunării Generale a membrilor unei Asociații de Proprietari din Condominiu (APC): oricine primește un link `/{uuid}` poate vota, fără pagină publică de start (homepage). Textul legal al buletinului este fix; doar variabilele (nr. APC, adresă, localitate, date, datele proprietarului) se completează din panoul de administrare, fără a modifica codul.

## Funcționalități

- Link unic de vot `https://domeniu/{uuid}` — fără autentificare, oricine are link-ul poate vota o singură dată.
- Linkul rămâne valabil până la **termenul-limită de remitere a buletinului** (configurabil per vot) și încă **30 de zile** (configurabil, `LINK_GRACE_DAYS`) după aceea, timp în care arată mesajul „votare închisă” / confirmarea votului; după acest interval devine invalid (HTTP 410).
- Textul buletinului respectă formatul legal cerut:
  - titlu centrat: *Buletin de VOT, al Adunării Generale Mixte a membrilor APC nr. {nr_apc}, din {str_apc}*;
  - pe același rând, data Adunării Generale (aliniată la stânga) și localitatea (aliniată la dreapta);
  - cele două paragrafe fixe (cu variabilele interpolate), aliniate simplu la stânga, identice pe pagina web și în PDF;
  - lista hotărârilor supuse votului (Da/Pro, Nu/Contra sau alte opțiuni definite de admin);
  - semnătura olografă la final.
- Semnătură olografă (desenată cu mouse/deget/stylus) obligatorie la finalul buletinului — salvată ca imagine și inclusă în PDF-ul de confirmare (font Unicode inclus, diacriticele românești se afișează corect în PDF).
- Generare automată a unui PDF „buletin de vot - confirmare” pentru fiecare vot (text legal, hotărâri + vot, semnătură, data/ora, id-ul votului).
- Trimitere automată a confirmării pe email, cu PDF-ul atașat, via SMTP — configurabil complet din panoul de administrare (host, port, user, parolă, TLS, subiect, conținut), nu doar din `.env`.
- Panou de administrare (user + parolă):
  - editor de conținut pentru buletin: nr. APC, adresă, localitate, data Adunării, termenul-limită, tip proprietate, lista de hotărâri;
  - generare în masă de link-uri personalizate (nume, telefon, adresă, email, nr. proprietate pentru fiecare proprietar) sau link-uri goale de completat ulterior;
  - export CSV, **checklist** cu cine a votat și cine nu (fără a arăta conținutul votului — vot secret), rezultate agregate pe hotărâre.
- Tot sistemul rulează în Docker (un singur container pentru backend + build-ul React, plus opțional Caddy pentru HTTPS automat).

## Stack tehnic

- **Backend:** Python (FastAPI) + SQLAlchemy + SQLite (fișier persistent, fără server de bază de date separat de administrat) + ReportLab (PDF, cu fontul DejaVu Sans inclus pentru diacritice) + `smtplib` (email).
- **Frontend:** React (Vite) — pagina publică de vot + panoul de administrare, SPA servit tot de backend (un singur container).
- **Docker:** build multi-stage (Node → build React, apoi Python runtime care servește API-ul și fișierele React), `compose.yaml` + `Dockerfile` la rădăcina proiectului.

## Pornire rapidă

```bash
cp .env.example .env
# editează .env: SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, PUBLIC_BASE_URL

docker compose up -d --build
```

Aplicația pornește pe `http://localhost:8000` (sau portul din `APP_PORT`). Panoul de administrare este la `/admin`.

### Cu HTTPS automat (Caddy), pentru un domeniu public precum `vot.aalto.md`

```bash
# în .env: PUBLIC_DOMAIN=vot.aalto.md, PUBLIC_BASE_URL=https://vot.aalto.md
docker compose --profile https up -d --build
```

Caddy obține automat certificatul Let's Encrypt pentru domeniul din `PUBLIC_DOMAIN` și face proxy către container-ul `app`.

## Fluxul de utilizare

1. **Creează/editează votul** din `/admin` → „Voturi APC” → „Vot nou” sau „Editează conținut”: nr. APC, adresa condominiului, localitatea, data Adunării Generale cu prezență, termenul-limită de remitere a buletinului, tipul de proprietate și lista hotărârilor supuse votului (fiecare cu opțiunile Da/Pro, Nu/Contra sau custom).
2. **Generează link-uri** din `/admin/elections/{id}` → „Link-uri de vot & checklist”:
   - fie lipsești o listă de proprietari (un rând pe proprietar: `Nume Prenume; telefon; adresă; email; nr. proprietate`), iar fiecare link vine deja completat cu datele acelui proprietar;
   - fie generezi link-uri goale și completezi datele mai târziu (din API, `PUT /api/admin/tokens/{id}`).
3. **Configurează SMTP** din `/admin/smtp` dacă vrei ca proprietarii cu adresă de email asociată linkului să primească automat PDF-ul de confirmare.
4. Proprietarul deschide `https://domeniu/{uuid}`, vede buletinul cu datele lui deja completate, votează fiecare hotărâre, semnează olograf și trimite votul. Nu există pagină publică de start — doar linkurile individuale funcționează.
5. Urmărești în timp real cine a votat din checklist (`/admin/elections/{id}`) și rezultatele agregate din tab-ul „Rezultate”.

## Structura proiectului

```
backend/            FastAPI (API, modele, text legal fix, generare PDF, email, auth admin)
frontend/            React (Vite) — pagina de vot + panoul de admin
Dockerfile            build multi-stage (frontend + backend într-o singură imagine)
compose.yaml          serviciul app + (opțional) Caddy pentru HTTPS
Caddyfile             config Caddy pentru HTTPS automat
.env.example          variabile de configurare
```

## Note de securitate

- Schimbă `SECRET_KEY` și `ADMIN_PASSWORD` din `.env` înainte de a expune public aplicația.
- Parola SMTP este stocată în baza de date (editabilă din panou); pentru producție, rulează aplicația în spatele HTTPS (profilul `caddy` sau propriul reverse proxy) ca traficul (inclusiv cookie-ul de sesiune admin) să fie criptat.
- Fiecare link de vot poate fi folosit o singură dată; după ce s-a votat, linkul arată doar confirmarea și permite descărcarea PDF-ului, fără a permite revotarea.
- Fonturile DejaVu Sans incluse în `backend/app/fonts/` sunt licențiate liber (Bitstream Vera + Arev Fonts License), redistribuire permisă.
