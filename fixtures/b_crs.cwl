# Fixture B: output declares expected CRS EPSG:3857; the raster is EPSG:4326 -> fails in full mode only.
cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#", sos: "https://dfg-sos.github.io/ontologies/cwl#"}
$schemas: [https://dfg-sos.github.io/ontologies/eo-formats.owl]
class: CommandLineTool
baseCommand: cp
arguments: [$(inputs.src.path), out.tif]
inputs: {src: File}
outputs:
  raster:
    type: File
    format: eo:GeoTIFF
    sos:expectedCRS: "EPSG:3857"
    outputBinding: {glob: out.tif}
