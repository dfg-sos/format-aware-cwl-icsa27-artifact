# F1.2/F1.3: a broken format contract. The workflow input declares abstract eo:Raster, i.e. any raster is valid, but
# the step it feeds needs eo:GeoTIFF. cwltool accepts the workflow and checks only the labels of the given job: a
# GeoTIFF job (F1.2) completes in every runtime variant, a NetCDF raster (F1.3), which the contract admits, stops at
# cwltool's label check when it creates the consume job. The linter rejects Raster -> GeoTIFF without a job.
cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#", sos: "https://dfg-sos.github.io/ontologies/cwl#"}
$schemas: [https://dfg-sos.github.io/ontologies/eo-formats.owl]
class: Workflow
inputs:
  raster: {type: File, format: eo:Raster}
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  consume: {run: ../tools/consume_geotiff.cwl, in: {data: raster}, out: [size]}
