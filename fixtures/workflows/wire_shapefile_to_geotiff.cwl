# F1.1: Shapefile workflow input into a GeoTIFF step input (linter: incompatible).
cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#", sos: "https://dfg-sos.github.io/ontologies/cwl#"}
$schemas: [https://dfg-sos.github.io/ontologies/eo-formats.owl]
class: Workflow
inputs:
  roads: {type: File, format: eo:Shapefile, secondaryFiles: [^.shx, ^.dbf, ^.prj]}
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  consume: {run: ../tools/consume_geotiff.cwl, in: {data: roads}, out: [size]}
