# F4.2/OK.3: output declares LineString geometry; with points.geojson it fails in full mode, roads.geojson passes.
cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#", sos: "https://dfg-sos.github.io/ontologies/cwl#"}
$schemas: [https://dfg-sos.github.io/ontologies/eo-formats.owl]
class: CommandLineTool
baseCommand: cp
arguments: [$(inputs.src.path), out.geojson]
inputs: {src: File}
outputs:
  lines:
    type: File
    format: eo:GeoJSON
    sos:expectedCRS: "EPSG:4326"
    sos:expectedGeometryType: LineString
    outputBinding: {glob: out.geojson}
