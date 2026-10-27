# F1.4 (linter only): F1.1 with EDAM instead of the EO ontology: TIFF (format_3591) wired to NetCDF (format_3650).
cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [http://edamontology.org/EDAM.owl]
class: Workflow
inputs:
  src: {type: File, format: edam:format_3591}
outputs: []
steps:
  use:
    run: {class: CommandLineTool, baseCommand: "true", inputs: {f: {type: File, format: edam:format_3650}}, outputs: []}
    in: {f: src}
    out: []
