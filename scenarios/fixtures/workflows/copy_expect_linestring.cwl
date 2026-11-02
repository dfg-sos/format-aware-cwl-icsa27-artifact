# F4.2/F4.4/OK.3: output declares LineString geometry; points.geojson fails in metadata mode, roads_stray_point.geojson only in content mode, roads.geojson passes.
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
