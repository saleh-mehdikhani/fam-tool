# Family Data Repository

This repository contains **people data** used by the [fam tool](https://github.com/saleh-mehdikhani/fam-tool).  
The data is stored in YAML files, where each file represents a person in the family tree.

## ⚠️ Important Notes

- **Do not manually modify IDs** in the YAML files.  
  IDs are critical for maintaining consistency across the project. Changing them may break links between people and relationships.

- You may update **people attributes** (e.g., name, birthdate, occupation, notes, etc.), but keep the **ID field untouched**.

- Do **not create or delete files manually** in this repository.  
  All structural modifications (adding/removing people) must be done via the `fam` CLI to ensure project consistency.

## About fam tool

This repository was generated and is managed by the [fam tool](https://github.com/saleh-mehdikhani/fam-tool).  
The `fam` command-line tool keeps the data and graph repositories in sync.

## Contribution Guidelines

- Use `fam` commands to add, remove, or connect people.
- Avoid direct edits that may corrupt the structure.

---
