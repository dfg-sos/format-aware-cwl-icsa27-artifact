# OK.2, F2.4 (no .dbf: cwltool stops before any step): Shapefile workflow input into a Vector step input (linter: compatible).
cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#", sos: "https://dfg-sos.github.io/ontologies/cwl#"}
$schemas: [https://dfg-sos.github.io/ontologies/eo-formats.owl]
class: Workflow
inputs:
  roads: {type: File, format: eo:Shapefile, secondaryFiles: [^.shx, ^.dbf, ^.prj]}
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  consume: {run: ../tools/consume_vector.cwl, in: {data: roads}, out: [size]}
