# X.2: a GeoTIFF output annotated with sos:expectedGeometryType, which raster formats do not support.
# In full mode the service rejects the request (400) -> error: fails by default, a warning with
# --format-service-error warn. Other modes send no metadata and pass.
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
    sos:expectedGeometryType: Point
    outputBinding: {glob: out.tif}
