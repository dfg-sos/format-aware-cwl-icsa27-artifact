# Copies any file and declares the result GeoTIFF without looking at it (the label-stamping gap).
cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#", sos: "https://dfg-sos.github.io/ontologies/cwl#"}
$schemas: [https://dfg-sos.github.io/ontologies/eo-formats.owl]
class: CommandLineTool
baseCommand: cp
arguments: [$(inputs.src.path), $(inputs.name)]
inputs:
  src: File
  name: string
outputs:
  raster: {type: File, format: eo:GeoTIFF, outputBinding: {glob: $(inputs.name)}}
