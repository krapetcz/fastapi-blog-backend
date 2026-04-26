# Blog — formátovaný obsah, cover image a galerie

Rozšíření blogu o Markdown editor, náhledový obrázek a galerii pod článkem.

**Tento dokument je jediným zdrojem pravdy** pro obě repa (`fastapiblog` + `gbolblog`). Při změně v BE repu okamžitě zkopírovat do FE repa a naopak.

---

## Projekt v kostce

- **Frontend** (`gbolblog`): React 19, Vite, Tailwind CSS 4, Auth0 React. Lokálně `http://localhost:5173`.
- **Backend** (`fastapiblog`): FastAPI, SQLModel, Pydantic v2, SQLite, Auth0 JWT. Lokálně `http://localhost:8000`.
- **Autentizace**: Auth0 JWT, admin whitelist podle emailu v `.env`. Všechny write operace vyžadují admin.
- **Aktuální datový model**: `Article` s poli `id`, `title`, `content` (plain string), `created_at`.
- **Aktuální API**: `GET /articles/`, `GET /articles/{id}`, `POST`, `PUT`, `DELETE` (poslední tři admin-only).
- **Dva oddělené git repozitáře**, každý s vlastní větví `feature/formatted-content-and-images`.

## Cíl této iterace

1. **Formátovaný text** — H1, H2, odstavce, odrážky, tučné, kurzíva. Ukládá se jako Markdown do existujícího `Article.content`.
2. **Cover image** — jeden náhledový obrázek na článek, zobrazený v seznamu a na detailu.
3. **Galerie pod článkem** — seznam obrázků s alt textem, drag&drop pořadí, jednotná výška při renderování.

Explicitně **mimo scope**: obrázky vkládané do textu, slug v URL, autor, tagy, drafts, updated_at, search, SEO meta, komentáře.

---

## Klíčová designová rozhodnutí

Rozhodnuto v designové diskusi. Tato sekce je **uzavřená**, není-li dobrý důvod ji revidovat.

### Formátovaný text

- **MDXEditor** (`@mdxeditor/editor`) jako WYSIWYG editor v `ArticleForm`.
- **Toolbar pouze**: blok-type select (Paragraph, H1, H2), Bold, Italic, BulletList, Undo/Redo.
- **Ukládá se jako Markdown** do existujícího `Article.content`. Žádná změna schématu pro text.
- **Renderování** na detailu přes `react-markdown` + `remark-gfm` + `rehype-sanitize`.
- **Styly** přes Tailwind Typography (`prose` třída).
- Paragraphs vznikají stisknutím Enter v editoru, serializují se do MD s prázdným řádkem mezi nimi (MDXEditor to dělá automaticky).

### Obrázky — storage

- **Lokální disk**, složka `fastapiblog/images/`.
- FastAPI servíruje přes `StaticFiles("/images", ...)`.
- `images/*` v `.gitignore` (s `.gitkeep` pro zachování složky).
- Upload i mazání izolované za helper funkcemi `save_image(file) -> url` a `delete_image_file(url)` — pro snadné budoucí přepnutí na cloud storage.

### Obrázky — upload

- Endpoint `POST /images`, admin only.
- **Max velikost: 10 MB** (pokryje HEIC z iPhone, screenshoty z Retina displeje, běžné fotky z foťáku).
- **Whitelist formátů**: JPEG, PNG, WebP, HEIC/HEIF.
- **Pillow + pillow-heif**: soubor se otevře a znovu uloží ve stejném formátu, maximální kvalita. Toto:
  - Odstraní EXIF (včetně GPS).
  - Neutralizuje případný maligní payload.
  - Validuje, že je to vůbec obrázek.
- **HEIC se ukládá jako JPEG quality=95** (HEIC rendering v prohlížečích není univerzální).
- **Filename**: UUID + přípona.
- **Žádný resize** — rozlišení se zachovává.
- Odpověď: `{"url": "/images/{uuid}.{ext}"}`.

### Datový model — cover image

- Nový sloupec `Article.cover_image_url` (Optional[str]).
- Při změně nebo smazání článku se soubor na disku smaže.

### Datový model — galerie

Nová tabulka `GalleryImage`:

| pole | typ | poznámka |
|------|-----|----------|
| `id` | int | PK |
| `article_id` | int | FK na Article, cascade delete |
| `url` | str | URL z `/images/` |
| `alt` | str | default `""` |
| `order` | int | mezery 10, 20, 30... (ne sekvenční) |

Vztah `Article.gallery_images: List[GalleryImage]` s cascade delete.

**Proč mezery v `order`**: při reorderingu nemusíme přepočítávat všechny řádky, stačí vložit novou hodnotu mezi. Občas se dá znormalizovat.

### Mazání souborů

- Cesta: **při DELETE článku nebo při odebrání obrázku z galerie/cover se soubor smaže z disku**.
- Helper `delete_image_file(url)` — chybějící soubor neházet chybu, jen logovat.
- Volána z DELETE article, z PUT article (diff staré vs. nové galerie, diff starého vs. nového cover).

### Migrace schématu

- **Alembic** se zavádí v M2.
- Všechny budoucí změny schématu přes migrace.
- Pro SQLite `render_as_batch=True` v `alembic/env.py` (nutné pro ALTER TABLE operace).

### Drag & drop pořadí galerie

- `@dnd-kit/core` + `@dnd-kit/sortable` na frontendu.
- **Žádný samostatný PATCH endpoint**. Pořadí se ukládá jako součást PUT `/articles/{id}` — backend dostane celou galerii v novém pořadí a updatuje `order` pole.

---

## Datový model po této iteraci

### Article

| pole | typ | poznámka |
|------|-----|----------|
| `id` | int | PK |
| `title` | str | indexed |
| `content` | str | Markdown |
| `cover_image_url` | Optional[str] | URL nebo null |
| `created_at` | datetime | server-gen |

### GalleryImage (nová)

| pole | typ | poznámka |
|------|-----|----------|
| `id` | int | PK |
| `article_id` | int | FK, cascade delete |
| `url` | str | |
| `alt` | str | default `""` |
| `order` | int | mezery 10, 20, 30... |

---

## API kontrakt

### `POST /images`

- Auth: admin.
- Body: `multipart/form-data` s polem `file`.
- Odpověď **201**: `{"url": "/images/{uuid}.{ext}"}`.
- Chyby:
  - **413** Request Entity Too Large (> 10 MB).
  - **415** Unsupported Media Type (špatný formát).
  - **400** Bad Request (poškozený / nevalidní obrázek).
  - **401/403** unauth / neadmin.

### `GET /articles/`

- Veřejné.
- Odpověď: list `ArticleRead` s `cover_image_url`.
- **`gallery_images` NENÍ v seznamu** (performance).

### `GET /articles/{id}`

- Veřejné.
- Odpověď: `ArticleReadDetail` včetně `gallery_images` seřazených podle `order` vzestupně.

### `POST /articles/`

- Auth: admin.
- Body:
  ```json
  {
    "title": "...",
    "content": "... Markdown ...",
    "cover_image_url": "/images/abc.jpg",
    "gallery_images": [
      {"url": "/images/def.jpg", "alt": "popis", "order": 10},
      {"url": "/images/ghi.jpg", "alt": "jiný popis", "order": 20}
    ]
  }
  ```
- `cover_image_url` může být `null`, `gallery_images` může být prázdný array.

### `PUT /articles/{id}`

- Auth: admin.
- Body jako POST.
- Server:
  - Pokud `cover_image_url` se změnil nebo je null a předtím nebyl — smazat starý soubor.
  - Diff stará vs. nová galerie podle URL:
    - URL zmizely z nové → smazat soubory + smazat GalleryImage řádky.
    - URL přibyly v nové → vytvořit GalleryImage řádky.
    - URL v obou → update `alt` a `order`.

### `DELETE /articles/{id}`

- Auth: admin.
- Server:
  - Smazat cover soubor (pokud existuje).
  - Smazat všechny gallery soubory.
  - Smazat článek (cascade smaže GalleryImage řádky).

---

## Mílníky

Každý mílník je end-to-end testovatelný checkpoint. Na další nepokračovat, dokud aktuální neprojde kritérii hotovo.

### M1 — Markdown editor (FE only)

- **BE změny**: žádné.
- **FE změny**: MDXEditor v ArticleForm, react-markdown na detailu, Tailwind Typography.
- **Hotovo když**:
  - Toolbar funguje: BlockType (P, H1, H2), Bold, Italic, BulletList, Undo/Redo.
  - Existující články se stále čtou a editují (Markdown je zpětně kompatibilní s plain textem).
  - Na detail stránce se content renderuje s formátováním.

### M2 — Schema + Alembic (BE only)

- **BE změny**: zavedení Alembicu, `Article.cover_image_url`, tabulka `GalleryImage`, první migrace.
- **FE změny**: minimální (volitelně skrýt staré placeholdery).
- **Hotovo když**:
  - `alembic upgrade head` proběhne čistě.
  - `GET /articles/` vrací existující články s `cover_image_url: null`.
  - `GET /articles/{id}` vrací `gallery_images: []`.

### M3 — Upload endpoint (BE only, testovaný curlem)

- **BE změny**: `POST /images`, Pillow + pillow-heif, validace, re-encode, StaticFiles mount, helper funkce.
- **FE změny**: žádné.
- **Hotovo když**:
  - Curl s JPG, PNG, HEIC, screenshotem → URL, soubor na disku, EXIF pryč.
  - Curl > 10 MB → 413, non-image → 400/415, unauth → 401/403.
  - `GET /images/{uuid}.{ext}` vrátí soubor.

### M4 — Cover image end-to-end

- **BE změny**: ArticleCreate/Update přijímá `cover_image_url`, cleanup souborů při změně/smazání.
- **FE změny**: `ImageUpload` komponenta, integrace do ArticleForm, zobrazení v seznamu + na detailu.
- **Hotovo když**:
  - Vytvořím článek s cover → thumbnail v seznamu, hero na detailu.
  - Nahradím cover → starý soubor z `images/` zmizel.
  - Odstraním cover → soubor zmizel.
  - Smažu článek → cover soubor zmizel.

### M5 — Galerie end-to-end (bez drag&drop)

- **BE změny**: ArticleCreate/Update přijímá `gallery_images`, diff logika při PUT, cleanup při DELETE.
- **FE změny**: `GalleryEditor` komponenta (multi-upload, alt input, remove), zobrazení galerie na detailu s uniform výškou.
- **Hotovo když**:
  - Nahraju 5 obrázků, vyplním alt, uložím.
  - Na detailu vidím galerii pod článkem (h-48, object-contain, flex wrap).
  - `<img alt="...">` má správný alt.
  - Odeberu 2 obrázky + uložím → soubory z disku zmizely.
  - Smažu článek → všechny soubory zmizely.

### M6 — Drag & drop pořadí

- **BE změny**: žádné nové (M5 už přijímá `order` v PUT body).
- **FE změny**: `@dnd-kit` na thumbnails v GalleryEditor, přepočet `order` při dragEnd.
- **Hotovo když**:
  - Přetáhnu obrázek → pořadí se okamžitě změní v UI.
  - Uložím + reload → pořadí drží.
  - Klávesnicová navigace drag&drop funguje.
  - Detail stránka respektuje nové pořadí.

### M7 — Polish

- Loading states (spinner během uploadu).
- Error messages v UI ("Soubor je moc velký", "Neplatný formát").
- Empty states (bez cover, bez galerie).
- A11y (alt, aria-label, focus).
- **Volitelně**: lightbox na klik (`yet-another-react-lightbox`).

---

## Git strategie

- Obě repa, větev **`feature/formatted-content-and-images`**.
- Commit message konvence: `[M{N}] <popis>`, např. `[M3] Add POST /images endpoint with Pillow re-encode`.
- Po každém mílníku push na feature větev.
- Merge do `main` až po M7 nebo podle komfortu (třeba po M4, pokud chceš průběžně mergovat).

---

## Konvence pro AI agenty (Claude Code)

- Respektovat existující styl kódu v repu.
- Žádné velké refaktory mimo scope aktuálního mílníku.
- Před instalací nového balíčku ověřit, že není už v `requirements.txt` / `package.json`.
- **Před implementací mílníku**: přečíst `PROJECT_SPEC.md`, přečíst příslušný TASKS.md, shrnout svůj plán ve 3–5 větách a počkat na OK od uživatele.
- **Po dokončení mílníku**: shrnout, co bylo uděláno, ukázat klíčové diffs, navrhnout commit message.
- Pokud některá technická volba nevychází (např. API knihovny je jiné než v dokumentu), **raději se zeptat** než hádat.

---

## Vědomě odložené věci

Tyto věci sice dávají smysl, ale **nejsou součástí této iterace**. Při psaní kódu nepřidávat, nepřipravovat na ně speciálně (kromě toho, že schéma je rozšiřitelné).

- Slug v URL (`/articles/muj-post`).
- Autor (z Auth0 claimů).
- Tagy / kategorie.
- Draft vs. published.
- `updated_at`.
- Search.
- SEO meta tagy, OG image.
- Komentáře.
- Obrázky uvnitř Markdown textu.
- Resize obrázků na server-side.
- Cloud storage místo lokálního disku.
