# OK.5 (linter only): EDAM, FASTA (format_1929) into a port accepting any sequence format (format_1919): a subclass.
cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [http://edamontology.org/EDAM.owl]
class: Workflow
inputs:
  src: {type: File, format: edam:format_1929}
outputs: []
steps:
  use:
    run: {class: CommandLineTool, baseCommand: "true", inputs: {f: {type: File, format: edam:format_1919}}, outputs: []}
    in: {f: src}
    out: []
