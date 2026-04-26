# Backend tasks — fastapiblog

Tento dokument je pro Claude Code pracujícího v repu `fastapiblog`.

**Nejprve si přečti `PROJECT_SPEC.md`** ve stejném repu — obsahuje kontext, datový model, API kontrakt a mílníky. Tento soubor je konkrétní úkolový plán pro backend.

---

## Než začneš

1. Přečti `PROJECT_SPEC.md`.
2. Přečti aktuální stav kódu: `main.py`, `app/api.py`, `app/models.py`, `app/db.py`, `app/auth.py`, `app/config.py`.
3. Založ větev: `git checkout -b feature/formatted-content-and-images`.
4. Shrň v několika větách, jak chápeš úkol **M2** (první BE mílník), a počkej na OK od uživatele, než začneš kódovat.

---

## Konvence

- Python 3.12+, FastAPI, SQLModel, Pydantic v2.
- Balíčky přidej do `requirements.txt` (nebo `pyproject.toml`, podle toho, co repo používá — ověř).
- Respektuj existující styl kódu a strukturu modulů.
- Virtual env je asi už nastaven — pokud ne, zeptej se uživatele.
- `fastapiblog.db` a `images/` nepatří do gitu.

---

## M1 — Markdown editor

**Backend se nemění.** Pokud čteš jako BE Claude Code, přeskoč na M2.

Kontext: FE ukládá obsah jako Markdown do existujícího `Article.content`. Pro backend je to pořád plain string. Žádná validace obsahu není potřeba.

---

## M2 — Schema a Alembic

### Úkoly

**1. Instalace:**

```bash
pip install alembic
```

Přidej do `requirements.txt`.

**2. Init Alembicu:**

```bash
alembic init alembic
```

**3. Konfigurace `alembic.ini`:**

```
sqlalchemy.url = sqlite:///fastapiblog.db
```

**4. Konfigurace `alembic/env.py`:**

- Importuj metadata z modelů:
  ```python
  from sqlmodel import SQLModel
  from app.models import *  # ať se všechny modely zaregistrují
  target_metadata = SQLModel.metadata
  ```
- V obou `run_migrations_online` i `run_migrations_offline` nastav `render_as_batch=True` v `context.configure(...)`. To je kritické pro SQLite — jinak ALTER TABLE nebude fungovat správně.

**5. Aktualizuj `app/models.py`:**

- Přidej do `Article`:
  ```python
  cover_image_url: Optional[str] = None
  gallery_images: List["GalleryImage"] = Relationship(
      back_populates="article",
      sa_relationship_kwargs={"cascade": "all, delete-orphan"},
  )
  ```
- Vytvoř novou třídu `GalleryImage`:
  ```python
  class GalleryImage(SQLModel, table=True):
      id: Optional[int] = Field(default=None, primary_key=True)
      article_id: int = Field(foreign_key="article.id", ondelete="CASCADE")
      url: str
      alt: str = ""
      order: int = 0
      article: Optional["Article"] = Relationship(back_populates="gallery_images")
  ```
- Ověř syntaxi `ondelete` ve tvé verzi SQLModel — v novějších to jde přes `Field(foreign_key=..., ondelete="CASCADE")`, ve starších to musíš řešit přes `sa_column=Column(...)`.

**6. Pydantic response/request modely:**

Pokud zatím používáš `Article` přímo jako response, rozděl to teď:

- `GalleryImageWrite` — body input: `url`, `alt`, `order`.
- `GalleryImageRead` — response: `id`, `url`, `alt`, `order`.
- `ArticleCreate` — body input: `title`, `content`, `cover_image_url`, `gallery_images: List[GalleryImageWrite]`.
- `ArticleUpdate` — stejné jako ArticleCreate.
- `ArticleRead` — response pro list: `id`, `title`, `content`, `cover_image_url`, `created_at` (bez gallery).
- `ArticleReadDetail` — response pro detail: `ArticleRead` + `gallery_images: List[GalleryImageRead]` (seřazené podle `order`).

**7. Uprav endpointy:**

- `GET /articles/` → vrací `List[ArticleRead]`.
- `GET /articles/{id}` → vrací `ArticleReadDetail`, gallery seřazená podle `order`.
- POST/PUT/DELETE v M2 ještě nemění — na ty dojde v M4 a M5.

**8. Vygeneruj a aplikuj migraci:**

```bash
alembic revision --autogenerate -m "Add cover_image_url and GalleryImage"
```

Zkontroluj vygenerovaný soubor v `alembic/versions/`. Autogen občas dělá neočekávané věci u SQLite FK a indexů — pokud vidíš něco divného, uprav ručně.

```bash
alembic upgrade head
```

### Test kritéria M2

- `alembic current` ukazuje novou revizi.
- `sqlite3 fastapiblog.db ".schema"` ukáže `cover_image_url` na Article a novou tabulku `galleryimage`.
- `GET /articles/` funguje, existující články mají `cover_image_url: null`.
- `GET /articles/{id}` vrací `gallery_images: []`.

### Commit

`[M2] Set up Alembic and extend schema for cover image and gallery`

---

## M3 — Upload endpoint

### Úkoly

**1. Instalace:**

```bash
pip install Pillow pillow-heif
```

Přidej do `requirements.txt`.

**2. Vytvoř modul `app/images.py`:**

Obsah:

- Registrace HEIF openeru (volat jednou při importu):
  ```python
  from pillow_heif import register_heif_opener
  register_heif_opener()
  ```
- `MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB`.
- `ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF"}` (Pillow formát názvy po otevření).
- Funkce `save_image(upload_file: UploadFile) -> str`:
  - Načte bytes.
  - Zkontroluje velikost, jinak `HTTPException(413, "File too large, max 10 MB")`.
  - `Image.open(BytesIO(contents))` — pokud selže, `HTTPException(400, "Invalid image file")`.
  - Zkontroluje `image.format in ALLOWED_FORMATS`, jinak `HTTPException(415, "Unsupported format")`.
  - Určí výstupní formát:
    - JPEG, PNG, WebP → stejný formát.
    - HEIF → JPEG (prohlížeče HEIC nativně nerenderují napříč platformami).
  - Vytvoří UUID název + příponu.
  - Uloží do `images/{uuid}.{ext}` s parametry:
    - JPEG: `quality=95, optimize=True`.
    - PNG: `optimize=True`.
    - WebP: `quality=95, method=6`.
  - Vrátí URL path `/images/{uuid}.{ext}`.
- Funkce `delete_image_file(url: str) -> None`:
  - Extrahuje filename z URL.
  - Zkusí smazat soubor z `images/`.
  - Pokud soubor neexistuje, jen log a return (žádná výjimka).
  - Pokud smazání selže z jiného důvodu, log error a return.

**3. Vytvoř router nebo endpoint v `app/api.py`:**

```python
@router.post("/images", status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    _: dict = Depends(require_admin),
):
    url = await save_image(file)
    return {"url": url}
```

Pozor: `save_image` by měla být async nebo volaná přes `run_in_threadpool` — Pillow je sync a blokující.

**4. Mount StaticFiles v `main.py`:**

```python
from fastapi.staticfiles import StaticFiles
# ...
app.mount("/images", StaticFiles(directory="images"), name="images")
```

**5. Vytvoř složku `images/`:**

```bash
mkdir -p images
touch images/.gitkeep
```

**6. `.gitignore`:**

```
images/*
!images/.gitkeep
```

### Test kritéria M3

Získej admin JWT token stejným způsobem jako doposud.

```bash
# JPG
curl -i -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.jpg" \
  http://localhost:8000/images
# → 201 {"url":"/images/xxx.jpg"}

# HEIC z iPhone
curl -i -H "Authorization: Bearer $TOKEN" \
  -F "file=@iphone.heic" \
  http://localhost:8000/images
# → 201 {"url":"/images/xxx.jpg"}  (HEIC převeden na JPEG)

# Screenshot PNG
curl -i -H "Authorization: Bearer $TOKEN" \
  -F "file=@screenshot.png" \
  http://localhost:8000/images
# → 201 {"url":"/images/xxx.png"}

# > 10 MB
curl -i -H "Authorization: Bearer $TOKEN" \
  -F "file=@big.jpg" \
  http://localhost:8000/images
# → 413

# Non-image
curl -i -H "Authorization: Bearer $TOKEN" \
  -F "file=@readme.md" \
  http://localhost:8000/images
# → 400

# Bez auth
curl -i -F "file=@test.jpg" http://localhost:8000/images
# → 401

# GET
curl -i http://localhost:8000/images/xxx.jpg
# → 200, Content-Type: image/jpeg
```

Ověř odstranění EXIF (pokud máš `exiftool`):

```bash
exiftool images/xxx.jpg
# → minimální metadata, bez GPS
```

### Commit

`[M3] Add POST /images endpoint with Pillow re-encode and HEIC support`

---

## M4 — Cover image end-to-end

### Úkoly

**1. Pydantic schémata (už z M2):**

Zkontroluj, že `ArticleCreate` a `ArticleUpdate` mají `cover_image_url: Optional[str] = None`. Pokud ne, přidej.

**2. `POST /articles/`:**

- Přijmi `cover_image_url` z body.
- Ulož do DB.

**3. `PUT /articles/{id}`:**

- Načti stávající article.
- Pokud `article.cover_image_url != new_cover_image_url`:
  - Pokud `article.cover_image_url` není None, zavolej `delete_image_file(article.cover_image_url)`.
  - Nastav nový.
- Ulož.

**4. `DELETE /articles/{id}`:**

- Načti article.
- Pokud `cover_image_url` není None, zavolej `delete_image_file`.
- Smaž article (gallery cleanup je v M5).

### Test kritéria M4

- POST s `cover_image_url` → článek má cover, GET ho vrací.
- PUT s novým `cover_image_url` → starý soubor zmizel z `images/`, nový tam je.
- PUT s `cover_image_url: null` → soubor zmizel, DB má null.
- DELETE → soubor zmizel.

### Commit

`[M4] Integrate cover_image_url into article CRUD with file cleanup`

---

## M5 — Galerie end-to-end (bez drag&drop)

### Úkoly

**1. Pydantic schémata:**

`ArticleCreate.gallery_images: List[GalleryImageWrite] = []` (pokud není z M2).

**2. `POST /articles/`:**

- Ulož Article.
- Pro každou položku v `gallery_images` vytvoř `GalleryImage` řádek s `article_id=article.id`.

**3. `PUT /articles/{id}`:**

Toto je nejsložitější část. Logika:

```
old_images = {img.url: img for img in article.gallery_images}
new_images = {img.url: img for img in body.gallery_images}

# Smazat obrázky, co zmizely z nové galerie
for url in old_images.keys() - new_images.keys():
    delete_image_file(url)
    session.delete(old_images[url])

# Přidat nové
for url in new_images.keys() - old_images.keys():
    new_row = GalleryImage(
        article_id=article.id,
        url=url,
        alt=new_images[url].alt,
        order=new_images[url].order,
    )
    session.add(new_row)

# Update existující (alt, order)
for url in old_images.keys() & new_images.keys():
    old_images[url].alt = new_images[url].alt
    old_images[url].order = new_images[url].order
```

Commit session.

**4. `DELETE /articles/{id}`:**

- Pro každý `gallery_images` řádek zavolej `delete_image_file(url)`.
- Smaž article — cascade smaže řádky.

### Test kritéria M5

- POST se 3 gallery obrázky a různými alt texty → `GET /articles/{id}` vrací 3 obrázky v pořadí podle `order`.
- PUT se 2 obrázky (odstranil jsem 1) → soubor z `images/` zmizel, DB má 2 řádky.
- PUT se změněným alt u existujícího obrázku → alt se aktualizuje.
- PUT s novým obrázkem → DB má nový řádek.
- DELETE → všechny gallery soubory zmizely.

### Commit

`[M5] Integrate gallery_images into article CRUD with diff logic`

---

## M6 — Drag & drop pořadí

Backend se **skoro nemění** — pořadí je součást `gallery_images` v PUT body, už z M5.

### Úkoly

1. Ověř, že M5 update logika respektuje nové `order` hodnoty (měla by).
2. Žádný samostatný PATCH endpoint nevytvářet.

### Test kritéria M6

- PUT s galerií v novém pořadí (jiné `order` hodnoty) → `GET /articles/{id}` vrací obrázky v novém pořadí.

### Commit

Pokud nic neměníš, žádný commit v BE. Mílník je implementovaný výhradně na FE.

---

## M7 — Polish

### Úkoly

1. **Konzistentní error odpovědi:**
   - Všechny HTTPException mají čitelný `detail`.
   - 413 pro velký soubor, 415 nebo 400 pro špatný formát.
2. **Logging:**
   - Log při uploadu (filename, size, výsledný format).
   - Log při mazání (success / fail / not-found).
3. **Cleanup:**
   - Žádné `print()` v produkčních cestách.
   - Docstrings u nových funkcí.

### Test kritéria M7

Manuální průchod edge case scenáři. Zkontroluj, že všechny chyby jsou srozumitelné.

### Commit

`[M7] Polish error handling and logging`

---

## Přehled commitů

- `[M2] Set up Alembic and extend schema for cover image and gallery`
- `[M3] Add POST /images endpoint with Pillow re-encode and HEIC support`
- `[M4] Integrate cover_image_url into article CRUD with file cleanup`
- `[M5] Integrate gallery_images into article CRUD with diff logic`
- `[M7] Polish error handling and logging`

Po každém mílníku: `git push origin feature/formatted-content-and-images`, pak uživatel spustí FE Claude Code a provede end-to-end test.
