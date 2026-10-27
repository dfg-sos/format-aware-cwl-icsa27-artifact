| ID | Injected fault | `off` | `lint` | `basic` | `structural` | `full` | Other variants | Where it stops |
|---|---|---|---|---|---|---|---|---|
| F1.1 | Shapefile input wired to a GeoTIFF port | 1 | **1** | 1 | 1 | 1 |  | linter: before any job; otherwise cwltool's label check when it creates the `consume` job |
| F1.2 | workflow input declares abstract `eo:Raster`, wired to a GeoTIFF port; the job passes a valid GeoTIFF | 0 | **1** | 0 | 0 | 0 |  | linter only, before any job; no runtime variant sees a fault with this job |
| F1.3 | as F1.2, the job passes a valid NetCDF raster (`eo:NetCDF_CF`, a `Raster`) | 1 | **1** | 1 | 1 | 1 |  | as F1.1 |
| F1.4 | F1.1 with EDAM instead of the EO ontology, TIFF wired to a NetCDF port |  | **1** |  |  |  |  | linter |
| F1.5 | F1.2 with EDAM, input accepts any sequence format (abstract), wired to a FASTA port |  | **1** |  |  |  |  | linter |
| F2.1 | workflow input `roads.geojson` labelled GeoTIFF by the job | 0 | 0 | **1** | 1 | 1 |  | input check of `consume`; `consume` not run |
| F2.2 | GeoJSON content named `roads_as.tif`, labelled GeoTIFF | 0 | 0 | 0 | 0 | **1** |  | as F2.1 |
| F2.3 | F2.1 in another domain: `reads.fastq` labelled EDAM FASTA (validator plug-in) | 0 | 0 | **1** | 1 | 1 |  | input check of `consume`; `consume` not run |
| F2.4 | F2.2 in another domain: FASTQ content named `reads_as.fasta`, labelled EDAM FASTA (validator plug-in) | 0 | 0 | 0 | 0 | **1** |  | as F2.3 |
| F3.1 | a tool writes GeoJSON as `out.geojson` and labels it GeoTIFF | 0 | 0 | **1** | 1 | 1 |  | output check of `relabel`; `consume` not run |
| F3.2 | as F3.1, but named `out.tif` | 0 | 0 | 0 | 0 | **1** |  | as F3.1 |
| F3.3 | F3.2 with all steps in `alpine` containers | 0 | 0 | 0 | 0 | **1** |  | as F3.1 |
| F4.1 | GeoTIFF in EPSG:4326, output declares `sos:expectedCRS: EPSG:3857` | 0 | 0 | 0 | 0 | **1** |  | output check of the tool |
| F5.1 | Point GeoJSON, output declares `sos:expectedGeometryType: LineString` | 0 | 0 | 0 | 0 | **1** |  | output check of the tool |
| F6.1 | GeoTIFF truncated at 64 bytes | 0 | 0 | 0 | 0 | **1** |  | as F2.1 |
| F6.2 | FASTA whose last record has no sequence, labelled EDAM FASTA (validator plug-in) | 0 | 0 | 0 | 0 | **1** |  | as F2.3 |
| OK.1 | none, a valid GeoTIFF into the F2 workflow | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.2 | none, Shapefile into an `eo:Vector` port (subclass, multi-file format) | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.3 | none, the F5.1 tool with LineStrings | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.4 | none, unannotated output (skipped, not sent to the service) | 0 |  | 0 | 0 | 0 |  | completes |
| OK.5 | none, EDAM, FASTA into a port accepting any sequence format (subclass) |  | 0 |  |  |  |  | completes |
| OK.6 | none, a valid FASTA into the F2.3 workflow (EDAM, validator plug-in) | 0 | 0 | 0 | 0 | 0 |  | completes |
| X.1 | output labelled `eo:WKB`, which the service cannot validate: `UNCERTAIN` | 0 | 0 | 0 | 0 | 0 | uncertain-fail: 1 | completes with a warning; with `--format-uncertain fail`: output check of the tool |
| X.2 | `sos:expectedGeometryType` on a GeoTIFF: the service rejects the request in full mode (`ERROR`) | 0 | 0 | 0 | 0 | 1 | full-service-error-warn: 0 | full: output check of the tool; with `--format-service-error warn` it completes with a warning |
| X.3 | EO formats checked against EDAM, which does not define them (`unknown-format`) |  | 1 |  |  |  |  | linter |
