# Copies any file and declares the result EDAM FASTA without looking at it (the label-stamping gap).
cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [http://edamontology.org/EDAM.owl]
class: CommandLineTool
baseCommand: cp
arguments: [$(inputs.src.path), $(inputs.name)]
inputs:
  src: File
  name: string
outputs:
  seqs: {type: File, format: edam:format_1929, outputBinding: {glob: $(inputs.name)}}
