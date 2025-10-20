# Commentaires SCSS compatibles `up-bulk-plugins-installer`

## Objectif

- **[Manifest SCSS]** Décrire les métadonnées des fichiers `.scss` sans polluer le CSS final.
- **[Parsing]** `manifest_build_scss.py` lit les lignes d’en-tête commençant par `//` pour alimenter `manifest.json`.

## Format général

Commentaires mono-ligne (`//`) placés au tout début du fichier, avant toute autre instruction.

```scss
// Slug: identifiant-unique
// Nom: Nom lisible
// Description: Résumé court
// Version: 1.0.0
// Catégories: Catégorie1, Catégorie2
// Type: style
// Files: clé=chemin|clé=chemin
// Install: style=assets/scss
// Preview: chemin/image.png
```

## Clés requises

- **`Slug`** : identifiant unique du module (`style-form-contact`).
- **`Nom`** : libellé lisible (`Style Formulaire Contact`).
- **`Description`** : résumé de l’utilité du SCSS.
- **`Version`** : version semver (défaut `1.0.0`).
- **`Catégories`** : liste séparée par `,`, `;` ou `|`.
- **`Type`** : généralement `style` pour un fichier SCSS.
- **`Install`** : destination (ex. `style=assets/scss/forms`).

## Clés optionnelles

- **`Files`** : ressources complémentaires (ex. `map=assets/scss/maps/_colors.scss`).
- **`Preview`** : visuel d’aperçu.
- **`Requires`** : dépendances (`bootstrap`, `variables.scss`).

## Exemple

```scss
// Slug: form-grid
// Nom: Form Grid Styles
// Description: Styles du formulaire de contact en grille responsive.
// Version: 1.0.0
// Catégories: SCSS, Formulaire
// Type: style
// Install: style=assets/scss/forms

.contact-form-grid {
  display: grid;
  gap: 1rem;
}
```

## Bonnes pratiques

- **[Position]** Garder les commentaires sans ligne vide avant/import pour que le script les détecte.
- **[Nettoyage]** Utiliser `//` plutôt que `/* ... */` afin que le CSS compilé reste propre.
- **[Synchronisation]** Après modification, exécuter `python3 manifest_build_scss.py --output manifest.json`.
- **[Slug unique]** S’assurer qu’aucun autre fichier du sous-module ne partage le même `Slug`.

## Ressources

- `manifest_build_scss.py` : script de génération adapté aux fichiers SCSS.
- `SOUS_MODULES_INSTALLATION.md` : initialisation des sous-modules.
- `AJOUTER_SUBMODULE.md` : procédure d’ajout d’un sous-module.
- `COMMENTAIRES_MANIFEST.md` : format générique pour PHP/JS.
