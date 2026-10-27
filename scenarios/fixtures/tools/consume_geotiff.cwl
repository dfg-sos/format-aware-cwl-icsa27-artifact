cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#", sos: "https://dfg-sos.github.io/ontologies/cwl#"}
$schemas: [https://dfg-sos.github.io/ontologies/eo-formats.owl]
class: CommandLineTool
baseCommand: [wc, -c]
stdout: size.txt
inputs:
  data:
    type: File
    format: eo:GeoTIFF
    inputBinding: {position: 1}
outputs:
  size: stdout
