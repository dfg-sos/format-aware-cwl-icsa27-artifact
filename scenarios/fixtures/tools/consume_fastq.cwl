cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [http://edamontology.org/EDAM.owl]
class: CommandLineTool
baseCommand: [wc, -c]
stdout: size.txt
inputs:
  data:
    type: File
    format: edam:format_1930
    inputBinding: {position: 1}
outputs:
  size: stdout
