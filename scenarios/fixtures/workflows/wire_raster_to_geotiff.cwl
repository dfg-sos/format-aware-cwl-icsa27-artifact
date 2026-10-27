# F1.2/F1.3: the workflow input accepts any raster (abstract eo:Raster), but the step it feeds needs eo:GeoTIFF.
# cwltool checks the labels of the files of one job only: a GeoTIFF job (F1.2) passes every runtime variant,
# a NetCDF raster (F1.3) is a valid workflow input and fails cwltool's label check at consume.
# The linter compares the declared formats and reports Raster -> GeoTIFF as incompatible without a job.
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
