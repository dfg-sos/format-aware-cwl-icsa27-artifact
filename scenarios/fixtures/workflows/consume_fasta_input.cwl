# F2.3/F2.4/F6.2/OK.6: consume_input.cwl with EDAM FASTA (format_1929), validated by the format-validator-bio plugin.
# Vanilla cwltool runs consume. The runner stops at consume's input check, so consume never runs:
# F2.3 (reads.fastq) in basic mode, F2.4 (FASTQ content named .fasta) and F6.2 (truncated FASTA) only in full.
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
