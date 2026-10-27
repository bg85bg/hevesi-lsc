# NEO24-Hevesi LSC – meccsek és tabellák

A klub mind a 14 csapatának menetrendje, eredményei és (nem hivatalos) tabellái egy oldalon.

- **Honlap:** `index.html` – a `data/klub.json` fájlból dolgozik.
- **Adatok:** `scripts/build.py` tölti le az MLSZ adatbankból (adatbank.mlsz.hu).
- **Frissítés:** a `.github/workflows/frissites.yml` kétnaponta lefut, frissíti az adatokat és újra közzéteszi az oldalt. Kézzel is indítható: **Actions → Frissítés és közzététel → Run workflow**.

A tabellák a lejátszott meccsek eredményeiből számoltak (győzelem 3, döntetlen 1 pont; holtversenyben gólkülönbség, majd több rúgott gól), levont pontokat és zöld asztalos döntéseket nem tartalmaznak.
