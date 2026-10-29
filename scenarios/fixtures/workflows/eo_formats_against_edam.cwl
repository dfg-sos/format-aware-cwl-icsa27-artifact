# X.2 (linter only): EO formats checked against EDAM, which does not define them: unknown-format, not incompatible.
cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/", eo: "https://dfg-sos.github.io/ontologies/eo-formats#"}
$schemas: [http://edamontology.org/EDAM.owl]
class: Workflow
inputs:
  src: {type: File, format: eo:Shapefile}
outputs: []
steps:
  use:
    run: {class: CommandLineTool, baseCommand: "true", inputs: {f: {type: File, format: eo:Vector}}, outputs: []}
    in: {f: src}
    out: []
