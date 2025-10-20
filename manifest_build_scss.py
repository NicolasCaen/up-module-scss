#!/usr/bin/env python3
"""Gabarit de génération de manifest pour un sous-module UP Functions.

Copiez ce fichier en `build_manifest.py` dans chaque dépôt (ou sous-module)
puis exécutez `python3 build_manifest.py`. Le script analysera les fichiers
PHP/JS/SCSS en cherchant un bloc PHPDoc/JsDoc ou des commentaires `//` en
en-tête pour extraire les métadonnées nécessaires au manifest consommé par le
plugin `up-bulk-plugins-installer`.

Champs reconnus dans le bloc `/** ... */` (un par ligne, format `Clé: valeur`) :

- `Slug` *(requis)* : identifiant unique de l'entrée.
- `Nom` : libellé lisible ; défaut = dérivé du slug ou du fichier.
- `Description` : courte description.
- `Version` : version sémantique, défaut `1.0.0`.
- `Catégories` : liste séparée par `,` / `;` / `|`.
- `Type` : clé primaire du fichier pour la section `files` (par défaut `php` ou
  `script` selon l'extension).
- `Files` / `Fichiers` : fichiers additionnels, format `clé=chemin` séparés par
  `,` / `;` / `|` (ex. `style=assets/css/foo.css;script=assets/js/foo.js`).
- `Install` : répertoire(s) de destination. Sans préfixe = valeur par défaut
  pour toutes les clés. Avec préfixe `Install (clé): valeur` ou via
  `Install: clé=chemin`. Exemple :
  - `Install: fonctions=wp-content/themes/mon-theme/functions`
  - `Install (php): functions/inc/up-cpt`
  - `Install: php=functions/inc/up-cpt;style=assets/css`
- `Preview` : chemin vers une image d'aperçu (optionnel).

Tout autre champ est ignoré. Le script ne traite que le premier bloc `/** ... */`
rencontré dans les 2 000 premiers caractères de chaque fichier.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

DOCBLOCK_PATTERN = re.compile(r"/\*\*(.*?)\*/", re.DOTALL)
FIELD_PATTERN = re.compile(r"^([A-Za-zÀ-ÖØ-öø-ÿ0-9 '\-_/()]+)\s*:\s*(.+)$")
DEFAULT_GLOBS = [
    "*.php",
    "*.js",
    "*.scss",
    "inc/**/*.php",
    "inc/**/*.js",
    "inc/**/*.scss",
    "src/**/*.php",
    "src/**/*.js",
    "src/**/*.scss",
]


@dataclass
class ManifestEntry:
    slug: str
    name: str
    description: str
    version: str
    categories: List[str]
    files: Dict[str, str]
    install: Dict[str, str]
    preview: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "categories": self.categories,
            "files": self.files,
            "install": self.install,
        }
        if self.preview:
            payload["preview"] = self.preview
        return payload


def normalize_key(key: str) -> str:
    normalized = unicodedata.normalize("NFKD", key.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).strip()


def parse_block_fields(block: str) -> Dict[str, object]:
    fields: Dict[str, object] = {}

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("*"):
            line = line.lstrip("*").strip()
        if not line:
            continue

        match = FIELD_PATTERN.match(line)
        if not match:
            continue

        raw_key, raw_value = match.groups()
        raw_key = raw_key.strip()
        raw_value = raw_value.strip()
        key_base, key_suffix = split_key(raw_key)

        if key_base == "install":
            install_map = fields.setdefault("install", {})
            assert isinstance(install_map, dict)
            update_mapping(install_map, raw_value, key_suffix)
        elif key_base in {"files", "fichiers"}:
            files_map = fields.setdefault("extra_files", {})
            assert isinstance(files_map, dict)
            update_mapping(files_map, raw_value, key_suffix)
        else:
            canonical = canonical_key(key_base)
            if canonical:
                fields[canonical] = raw_value

    return fields


def split_key(raw_key: str) -> tuple[str, Optional[str]]:
    suffix: Optional[str] = None
    if "(" in raw_key and raw_key.endswith(")"):
        base, _, suf = raw_key.partition("(")
        suffix = suf[:-1].strip()  # remove trailing ')'
        raw_key = base.strip()
    return normalize_key(raw_key).replace(" ", ""), (suffix.lower() if suffix else None)


def canonical_key(key: str) -> Optional[str]:
    mapping = {
        "slug": "slug",
        "nom": "name",
        "name": "name",
        "titre": "name",
        "description": "description",
        "resume": "description",
        "version": "version",
        "categorie": "categories",
        "categories": "categories",
        "categoriees": "categories",
        "type": "type",
        "preview": "preview",
        "vignette": "preview",
    }
    return mapping.get(key)


def update_mapping(target: Dict[str, str], raw_value: str, suffix: Optional[str]) -> None:
    pairs = parse_pairs(raw_value)
    if suffix:
        if pairs:
            # Si la valeur contient des paires, nous priorisons la clef explicite.
            for key, value in pairs.items():
                target[key.lower()] = value
        else:
            target[suffix] = raw_value
    else:
        if not pairs:
            target.setdefault("default", raw_value)
        else:
            for key, value in pairs.items():
                target[key.lower()] = value


def parse_pairs(raw_value: str) -> Dict[str, str]:
    pairs: Dict[str, str] = {}
    for part in re.split(r"[;,|]", raw_value):
        segment = part.strip()
        if not segment:
            continue
        if "=" in segment:
            key, value = segment.split("=", 1)
            pairs[key.strip().lower()] = value.strip()
    return pairs


def parse_doc_fields(path: Path) -> Dict[str, object]:
    content = path.read_text(encoding="utf-8")
    for match in DOCBLOCK_PATTERN.finditer(content):
        if match.start() > 2000:
            # On ne prend que les docblocks d'en-tête.
            break
        fields = parse_block_fields(match.group(1))
        if fields:
            return fields

    # Support des commentaires SCSS (lignes commençant par //)
    header_lines: List[str] = []
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if header_lines:
                break
            continue
        if stripped.startswith("//"):
            header_lines.append(stripped[2:].strip())
            continue
        # Toute autre ligne arrête la collecte si nous avions déjà des commentaires
        if header_lines:
            break
        break

    if header_lines:
        scss_block = "\n".join(header_lines)
        fields = parse_block_fields(scss_block)
        if fields:
            return fields

    return {}


def to_categories(raw: Optional[str]) -> List[str]:
    if not raw:
        return ["Modules"]
    items = [item.strip() for item in re.split(r"[;,|]", raw) if item.strip()]
    return items or ["Modules"]


def default_file_key(path: Path, override: Optional[str]) -> str:
    if override:
        return override.lower()
    suffix = path.suffix.lower()
    if suffix == ".js":
        return "script"
    if suffix in {".scss", ".css"}:
        return "style"
    return "php"


def default_install_path(rel_path: Path, file_key: str) -> str:
    parent = rel_path.parent.as_posix()

    if file_key in {"style", "css", "scss"}:
        base = "assets/scss"
    elif file_key in {"script", "js"}:
        base = "assets/js"
    else:
        base = "functions"

    if parent in ("", "."):
        return base
    return f"{base}/{parent}".rstrip("/")


def build_entry(base_dir: Path, path: Path, seen_slugs: Dict[str, Path]) -> Optional[ManifestEntry]:
    fields = parse_doc_fields(path)
    if not fields:
        return None

    rel_path = path.relative_to(base_dir).as_posix()
    slug = fields.get("slug") or path.stem
    slug = slug.strip()
    if not slug:
        return None

    if slug in seen_slugs:
        print(f"⚠️  Duplicate slug '{slug}' for {path} (already defined in {seen_slugs[slug]})", file=sys.stderr)
        return None
    seen_slugs[slug] = path

    name = path.name
    description = fields.get("description") or f"Module {name}"
    version = fields.get("version") or "1.0.0"
    categories = to_categories(fields.get("categories"))

    file_key = default_file_key(path, fields.get("type"))

    files: Dict[str, str] = {file_key: rel_path}
    extra_files: Dict[str, str] = fields.get("extra_files", {})  # type: ignore[assignment]
    if extra_files:
        for key, value in extra_files.items():
            files[key.lower()] = value

    install_map: Dict[str, str] = {}
    raw_install: Dict[str, str] = fields.get("install", {})  # type: ignore[assignment]
    for key, file_path in files.items():
        dest = (
            raw_install.get(key)
            or raw_install.get("default")
            or default_install_path(Path(file_path), key)
        )
        install_map[key] = dest.rstrip("/")

    preview = fields.get("preview")

    return ManifestEntry(
        slug=slug,
        name=name,
        description=description,
        version=version,
        categories=categories,
        files=files,
        install=install_map,
        preview=preview,
    )


def iter_source_files(base_dir: Path, patterns: Iterable[str]) -> Iterable[Path]:
    yield from sorted({
        file
        for pattern in patterns
        for file in base_dir.glob(pattern)
        if file.is_file() and not file.name.startswith(".")
    })


def build_manifest(base_dir: Path, patterns: Iterable[str]) -> List[ManifestEntry]:
    entries: List[ManifestEntry] = []
    seen: Dict[str, Path] = {}
    for path in iter_source_files(base_dir, patterns):
        entry = build_entry(base_dir, path, seen)
        if entry:
            entries.append(entry)
        else:
            print(f"ℹ️  Ignored {path} (aucune métadonnée valide)")
    return sorted(entries, key=lambda item: item.slug)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Génère manifest.json pour un sous-module UP.")
    parser.add_argument("--output", default="manifest.json", help="Chemin du manifest de sortie")
    parser.add_argument(
        "--glob",
        action="append",
        dest="globs",
        help="Patrons glob supplémentaires (répétable). Par défaut: %(default)s",
    )
    args = parser.parse_args(argv)

    base_dir = Path(__file__).resolve().parent
    patterns = args.globs if args.globs else DEFAULT_GLOBS

    entries = build_manifest(base_dir, patterns)
    if not entries:
        print("⚠️  Aucun élément généré. Vérifiez les blocs PHPDoc/JsDoc.", file=sys.stderr)
        return 1

    manifest = {"patterns": [entry.to_dict() for entry in entries]}
    output_path = (base_dir / args.output).resolve()
    output_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✅ Manifest généré ({len(entries)} entrées) → {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
