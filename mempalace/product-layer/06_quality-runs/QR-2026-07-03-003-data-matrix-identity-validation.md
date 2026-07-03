# QR-2026-07-03-003 - Data Matrix identity validation

## Purpose
Validate product-layer support for GTIN, batch/lot number, serial number, and derived GS1 DataMatrix-style identity payloads.

## Scope
Checked:
- Generated product attributes.
- CSV import identity string preservation.
- Product validation requirements.
- Digital Product Passport identity block.
- CSV, HTML, SVG, and UI identity surfaces.
- Metadata and quality config JSON.

## Results
- Passed: `python3 -B -m unittest discover -s tests -v`, 20 tests run, 17 passed, 3 live HTTP tests skipped because `TEST_BASE_URL` is unset.
- Passed: `python3 -m json.tool config/quality_rules.json`.
- Passed: `python3 -m json.tool config/metadata_schema.json`.
- Passed: `PYTHONPYCACHEPREFIX=/private/tmp/thebenpaul-pycache python3 -m py_compile app/app.py tests/test_app.py`.
- Failed:
- Skipped: live HTTP tests in the Codex sandbox.

## Observations
GTIN, batch/lot number, and serial number are now required generic product attributes. Product-layer derives `(01){gtin_14}(10){batch_lot_number}(21){serial_number}` for the Data Matrix payload and exposes GTIN plus serial as the globally unique product instance identity.

## Action items
- Run live HTTP tests from a host terminal or CI runner with network access.
- Confirm future data-layer exports populate `attributes.gtin`, `attributes.batch_lot_number`, and `attributes.serial_number`.

## Related links
- GitHub workflow:
- Logs:
- Release:
