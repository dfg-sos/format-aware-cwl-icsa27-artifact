# Bio F1.2/F1.3: EO F1.2/F1.3 with EDAM: the workflow input accepts any sequence format (abstract format_1919), but the step
# it feeds needs FASTA (format_1929). A FASTA job (F1.2) passes every runtime variant, a FASTQ job (F1.3, a sequence
# format too) is a valid workflow input and fails cwltool's label check at consume.
# The linter compares the declared formats and reports sequence format -> FASTA as incompatible without a job.
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
