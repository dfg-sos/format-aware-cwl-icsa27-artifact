# Bio F2.1/F2.2/F2.3/OK.1: consume_input.cwl with EDAM FASTA (format_1929), validated by the format-validator-bio plugin.
# Vanilla cwltool runs consume. The runner stops at consume's input check, so consume never runs:
# F2.1 (reads.fastq) in basic mode, F2.2 (FASTQ content named .fasta) in metadata mode; F2.3 (missing file) stops in cwltool.
cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [http://edamontology.org/EDAM.owl]
class: Workflow
inputs:
  seqs: {type: File, format: edam:format_1929}
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  consume: {run: ../tools/consume_fasta.cwl, in: {data: seqs}, out: [size]}
