# Bio OK.2: EO OK.2 with EDAM, FASTA (format_1929) workflow input into a step accepting any sequence format (format_1919): a subclass.
cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [http://edamontology.org/EDAM.owl]
class: Workflow
inputs:
  seqs: {type: File, format: edam:format_1929}
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  consume: {run: ../tools/consume_sequence.cwl, in: {data: seqs}, out: [size]}
