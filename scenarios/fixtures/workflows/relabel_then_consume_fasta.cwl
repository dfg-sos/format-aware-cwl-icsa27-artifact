# Bio F3.1/F3.2: EO F3.1/F3.2 with EDAM: a FASTQ file is labelled FASTA (format_1929) and consumed as FASTA.
# Vanilla cwltool succeeds. F3.1 (name out.fastq) fails in basic mode, F3.2 (out.fasta) in metadata mode.
cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [http://edamontology.org/EDAM.owl]
class: Workflow
inputs:
  src: File
  name: string
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  relabel: {run: ../tools/relabel_as_fasta.cwl, in: {src: src, name: name}, out: [seqs]}
  consume: {run: ../tools/consume_fasta.cwl, in: {data: relabel/seqs}, out: [size]}
