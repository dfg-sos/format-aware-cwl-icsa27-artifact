# Bio F1.1: EO F1.1 with EDAM: FASTQ (format_1930) workflow input into a FASTA (format_1929) step input (linter: incompatible).
cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [http://edamontology.org/EDAM.owl]
class: Workflow
inputs:
  seqs: {type: File, format: edam:format_1930}
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  consume: {run: ../tools/consume_fasta.cwl, in: {data: seqs}, out: [size]}
