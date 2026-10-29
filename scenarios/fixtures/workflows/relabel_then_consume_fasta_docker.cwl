# Bio F3.3: Bio F3.2 in containers: every step runs in alpine (DockerRequirement hint), so the checks
# go through DockerCommandLineJob (staged container paths, host paths via the pathmapper).
cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [http://edamontology.org/EDAM.owl]
class: Workflow
hints:
  DockerRequirement: {dockerPull: "alpine:3.20"}
inputs:
  src: File
  name: string
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  relabel: {run: ../tools/relabel_as_fasta.cwl, in: {src: src, name: name}, out: [seqs]}
  consume: {run: ../tools/consume_fasta.cwl, in: {data: relabel/seqs}, out: [size]}
