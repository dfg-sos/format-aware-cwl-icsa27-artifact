# Bio F1.2/F1.3: EO F1.2/F1.3 with EDAM. The workflow input declares any sequence format (abstract format_1919), but
# the step it feeds needs FASTA (format_1929). A FASTA job (F1.2) completes in every runtime variant, a FASTQ job
# (F1.3), which the contract admits, stops at cwltool's label check at consume.
# The linter rejects sequence format -> FASTA without a job.
cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [http://edamontology.org/EDAM.owl]
class: Workflow
inputs:
  seqs: {type: File, format: edam:format_1919}
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  consume: {run: ../tools/consume_fasta.cwl, in: {data: seqs}, out: [size]}
