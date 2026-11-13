# Sistem de Vot (buletin APC)

Sistem de votare online pentru buletinul de vot al Adunării Generale a membrilor unei Asociații de Proprietari din Condominiu (APC): oricine primește un link `/{uuid}` poate vota. Pagina de start `/` este o pagină albă, fără redirect automat către panoul de administrare. Textul legal al buletinului este fix; doar variabilele (nr. APC, adresă, localitate, date, datele proprietarului) se completează din panoul de administrare, fără a modifica codul.

## Funcționalități

- Link unic de vot `https://domeniu/{uuid}` — fără autentificare, oricine are link-ul poate vota o singură dată.
- Linkul rămâne valabil până la **termenul-limită de remitere a buletinului** (configurabil per vot) și încă **30 de zile** (configurabil, `LINK_GRACE_DAYS`) după aceea, timp în care arată mesajul „votare închisă” / confirmarea votului; după acest interval devine invalid (HTTP 410).
- Textul buletinului respectă formatul legal cerut:
  - titlu centrat: *Buletin de VOT, al Adunării Generale Mixte a membrilor APC nr. {nr_apc}, din {str_apc}*;
  - pe același rând, data Adunării Generale (aliniată la stânga) și localitatea (aliniată la dreapta);
  - cele două paragrafe legale fixe (cu variabilele interpolate), aliniate la stânga — apar **doar în PDF-ul generat și în emailul HTML de confirmare**, nu pe pagina web de vot;
  - lista întrebărilor supuse votului, cu numerotare liberă (`1`, `2`, `3`, `3.a`, `3.b` …) și opțiunile implicite „Pentru” / „Împotriva”;
  - semnătura olografă la final.
- **Întrebări condiționate (dependente):** la configurare, o întrebare poate depinde de răspunsul la o întrebare anterioară. Dacă răspunsul-părinte este cel ales (ex. „Pentru”), întrebarea dependentă devine inactivă și primește automat răspunsul configurat (ex. „Împotriva”); dacă părintele are alt răspuns (ex. „Împotriva”), întrebarea dependentă poate fi completată liber. Regula se aplică identic pe client și pe server, iar răspunsul automat este salvat și numărat la rezultate.
- **Datele proprietarului introduse de votant:** `{nume_prenume}`, `{phone}`, `{str_locatar}`, `{email}`, `{nr_proprietate}` — preluate din linkul generat de admin, dar editabile; validate atât în interfață, cât și pe server (lungime, caractere permise, format telefon/email) și salvate pe token înainte de generarea PDF-ului și a emailului.
- **Consimțământ GDPR:** căsuță obligatorie de acceptare a prelucrării datelor personale în scopul votării; data consimțământului este înregistrată în baza de date și în PDF.
- Semnătură olografă (desenată cu mouse/deget/stylus) obligatorie la finalul buletinului — salvată ca imagine și inclusă în PDF-ul de confirmare (font Unicode inclus, diacriticele românești se afișează corect în PDF).
- Generare automată a unui PDF „buletin de vot - confirmare” pentru fiecare vot (text legal, întrebări + vot, semnătură, data/ora, consimțământ GDPR, id-ul votului).
- Confirmare pe email configurabilă per vot: **cu atașament PDF** sau **fără atașament** (atunci emailul conține textul legal și linkul de descărcare a buletinului). Emailul este multipart (text simplu + HTML) și poate avea **copii CC/BCC** configurate per vot, trimise automat la fiecare confirmare.
- Trimiterea emailului folosește setările SMTP din panoul de administrare (host, port, user, parolă, TLS, subiect, conținut), nu doar variabile din `.env`.
- **Raport de rezultate către APC:** fiecare vot poate avea o adresă de email APC care primește rapoarte cu rezultatele:
  - automat la fiecare vot nou (opțional, per vot);
  - manual din panoul de administrare, tab-ul „Rezultate” (butonul „Trimite rezultatele pe email”);
  - automat o singură dată la încheierea votării (după `end_date_vot`), printr-un proces de fundal ușor care verifică periodic.
  Raportul conține rezultatele **în procente**, numărul de voturi, participarea și o **diagramă** (bare) pentru fiecare întrebare, atât în HTML, cât și în varianta text. O eroare de email nu blochează niciodată votul.
- **Dashboard public în timp real:** fiecare vot primește un identificator public aleator, diferit de link-urile de vot, la adresa `https://domeniu/{public_uuid}/dashboard`. Pagina afișează rezultatele agregate în procente și diagrame și se actualizează automat la fiecare 5 secunde. Link-ul dashboardului este inclus în rapoartele de email și în panoul de administrare.
- Panou de administrare (user + parolă):
  - autentificare cu credențiale inițiale simple și **schimbare obligatorie a parolei la prima conectare**; parola poate fi schimbată oricând din „Schimbă parola”, iar resetarea în caz de blocare se face controlat din `.env`;
  - editor de conținut pentru buletin: nr. APC, adresă, localitate, data Adunării, termenul-limită, tip proprietate, întrebări cu numerotare liberă și logică condiționată;
  - setări per vot pentru email: cu/fără atașament PDF, copii CC și BCC;
  - generare în masă de link-uri personalizate (nume, telefon, adresă, email, nr. proprietate pentru fiecare proprietar) sau link-uri goale de completat ulterior;
  - export CSV, **checklist** cu cine a votat și cine nu (fără a arăta conținutul votului — vot secret), rezultate agregate pe întrebare, link către dashboardul public și trimiterea manuală a raportului de rezultate.
- Tot sistemul rulează în Docker (un singur container pentru backend + build-ul React, ).

## Stack tehnic

- **Backend:** Python (FastAPI) + SQLAlchemy + SQLite (fișier persistent, fără server de bază de date separat de administrat) + ReportLab (PDF, cu fontul DejaVu Sans inclus pentru diacritice) + `smtplib` (email).
- **Frontend:** React (Vite) — pagina publică de vot, dashboardul public de rezultate și panoul de administrare, SPA servit tot de backend (un singur container).
- **Docker:** build multi-stage (Node → build React, apoi Python runtime care servește API-ul și fișierele React), `compose.yaml` + `Dockerfile` la rădăcina proiectului.

## Pornire rapidă

```bash
cp .env.example .env
# editează .env: SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, PUBLIC_BASE_URL

docker compose up -d --build
```

Aplicația pornește pe `http://localhost:8000` (sau portul din `APP_PORT`). Panoul de administrare este la `/admin`.

### Cont de administrare

- Credențiale inițiale simple: **`admin` / `admin`** (sau cele din `ADMIN_USERNAME` / `ADMIN_PASSWORD`).
- La prima autentificare, panoul **vă obligă să schimbați parola** (minimum 8 caractere) înainte de a putea administra voturile; până atunci, toate operațiunile din API sunt blocate (cu excepția schimbării parolei).
- Dacă baza de date există deja și nu mai știți parola (de exemplu, ați schimbat `ADMIN_PASSWORD` în `.env`, dar contul fusese deja creat), o puteți reseta din container, fără să depindeți de `.env`:

  ```bash
  docker compose exec app python -m app.reset_admin --password "parola-temporara"
  # apoi autentificare cu această parolă și schimbare din panou
  ```

- Alternativ, dacă serviciul folosește `env_file` (variantele anterioare de `compose.yaml`), resetarea se poate face și din `.env`:

  ```bash
  # în .env:
  # ADMIN_PASSWORD=parola-temporara
  # ADMIN_RESET_PASSWORD=true
  docker compose up -d
  ```

  Autentificați-vă cu `ADMIN_PASSWORD`, schimbați parola din panou, apoi puneți `ADMIN_RESET_PASSWORD=false`. Resetarea se execută o singură dată (marker `/data/.admin-reset-used`); pentru o nouă resetare, ștergeți markerul:
  `docker compose exec app rm /data/.admin-reset-used`.

> **Notă:** `compose.yaml` transmite containerului variabilele din `.env` (`SECRET_KEY`, `ADMIN_*`, `PUBLIC_BASE_URL`, `LINK_GRACE_DAYS`, `SMTP_*`). Dacă modificați `.env`, reporniți cu `docker compose up -d` ca modificările să ajungă în container. Linkul de vot și linkul dashboardului folosesc `PUBLIC_BASE_URL`.


## Fluxul de utilizare

1. **Creează/editează votul** din `/admin` → „Voturi APC” → „Vot nou” sau „Editează conținut”: nr. APC, adresa condominiului, localitatea, data Adunării Generale cu prezență, termenul-limită de remitere a buletinului, tipul de proprietate și întrebările supuse votului (numerotare liberă `1`, `2`, `3.a`…; opțiuni implicite „Pentru” / „Împotriva”). Tot aici alegi expedierea confirmării **cu sau fără atașament PDF**, precum și eventualele **copii CC/BCC**, setezi **adresa de email APC pentru rezultate** și opțiunea de a trimite raportul la fiecare vot nou, și poți seta o întrebare ca dependentă de răspunsul la una anterioară.
2. **Generează link-uri** din `/admin/elections/{id}` → „Link-uri de vot & checklist”:
   - fie lipsești o listă de proprietari (un rând pe proprietar: `Nume Prenume; telefon; adresă; email; nr. proprietate`), iar fiecare link vine deja completat cu datele acelui proprietar;
   - fie generezi link-uri goale și completezi datele mai târziu (din API, `PUT /api/admin/tokens/{id}`).
3. **Configurează SMTP** din `/admin/smtp` (necesar atât pentru confirmările pe email, cât și pentru rapoartele de rezultate către APC).
4. Proprietarul deschide `https://domeniu/{uuid}`, verifică/completează datele personale, răspunde la întrebări (cele condiționate se blochează automat dacă este cazul), bifează acordul GDPR, semnează olograf și trimite votul. Textul legal apare doar în PDF-ul și emailul de confirmare, nu pe pagina de vot. Pagina de start `/` este albă; panoul de administrare se accesează direct la `/admin/login`.
5. Urmărești în timp real cine a votat din checklist (`/admin/elections/{id}`) și rezultatele agregate din tab-ul „Rezultate”. De acolo poți:
   - deschide **dashboardul public** `/{public_uuid}/dashboard` și îl poți partaja membrilor APC (se actualizează automat, fără date personale);
   - trimite manual raportul de rezultate pe emailul APC.
6. La încheierea votării (`end_date_vot`), sistemul trimite automat **o singură dată** raportul final către adresa APC configurată (dacă SMTP este activ).

## Structura proiectului

```
backend/            FastAPI (API, modele, text legal fix, generare PDF, email, auth admin)
frontend/            React (Vite) — pagina de vot + panoul de admin
Dockerfile            build multi-stage (frontend + backend într-o singură imagine)
compose.yaml          serviciul app
.env.example          variabile de configurare
```

## Note de securitate

- Schimbă `SECRET_KEY` și parola de administrare din `.env` înainte de a expune public aplicația. Credențialele inițiale `admin` / `admin` sunt publice prin documentație; sistemul cere schimbarea parolei la prima autentificare, dar nu lăsați instanța expusă cu parola implicită nesolicitată.
- Parola SMTP este stocată în baza de date (editabilă din panou); pentru producție, rulează aplicația în spatele HTTPS (printr-un reverse proxy propriu) ca traficul (inclusiv cookie-ul de sesiune admin) să fie criptat.
- Fiecare link de vot poate fi folosit o singură dată; după ce s-a votat, linkul arată doar confirmarea și permite descărcarea PDF-ului, fără a permite revotarea.
- Dashboardul public folosește un identificator aleator separat (`public_uuid`) și afișează exclusiv rezultate agregate, fără date personale. Nu îl confundați cu link-urile de vot: cine are link-ul dashboardului vede rezultatele, dar nu poate vota.
- Raportul final se trimite o singură dată per vot; momentul trimiterii este reținut în baza de date (`results_final_email_sent_at`), deci o repornire a aplicației nu retrimite raportul.
- Datele personale introduse de votant sunt folosite exclusiv pentru organizarea votării; consimțământul GDPR este obligatoriu și înregistrat (dată + oră) în baza de date și în PDF.
- Fonturile DejaVu Sans incluse în `backend/app/fonts/` sunt licențiate liber (Bitstream Vera + Arev Fonts License), redistribuire permisă.
