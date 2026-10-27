# F1.5 (linter only): F1.2 with EDAM: the input accepts any sequence format (abstract format_1919), the step needs FASTA (format_1929).
cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [http://edamontology.org/EDAM.owl]
class: Workflow
inputs:
  src: {type: File, format: edam:format_1919}
outputs: []
steps:
  use:
    run: {class: CommandLineTool, baseCommand: "true", inputs: {f: {type: File, format: edam:format_1929}}, outputs: []}
    in: {f: src}
    out: []
