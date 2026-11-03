# Bio F5.2: consume_fasta_input.cwl for EDAM FASTQ (format_1930): a FASTQ cut off inside a record (reads_truncated.fastq)
# passes cwltool, basic and metadata mode (its first record is intact); content mode stops it at consume's input check.
# (FASTA cannot show this fault: a FASTA file cut off inside a sequence is still valid FASTA.)
cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [http://edamontology.org/EDAM.owl]
class: Workflow
inputs:
  seqs: {type: File, format: edam:format_1930}
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  consume: {run: ../tools/consume_fastq.cwl, in: {data: seqs}, out: [size]}
