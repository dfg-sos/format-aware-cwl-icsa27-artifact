# F3.3: F3.2 in containers: every step runs in alpine (DockerRequirement hint), so the checks
# go through DockerCommandLineJob (staged container paths, host paths via the pathmapper).
cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#", sos: "https://dfg-sos.github.io/ontologies/cwl#"}
$schemas: [https://dfg-sos.github.io/ontologies/eo-formats.owl]
class: Workflow
hints:
  DockerRequirement: {dockerPull: "alpine:3.20"}
inputs:
  src: File
  name: string
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  relabel: {run: ../tools/relabel_as_geotiff.cwl, in: {src: src, name: name}, out: [raster]}
  consume: {run: ../tools/consume_geotiff.cwl, in: {data: relabel/raster}, out: [size]}
