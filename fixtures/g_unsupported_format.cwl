# Fixture G: output labelled eo:WKB, a format the service cannot validate (no validator, not mapped).
# The service answers 400 "not supported" -> UNCERTAIN: a warning by default, a failure with --format-uncertain fail.
cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#"}
$schemas: [https://dfg-sos.github.io/ontologies/eo-formats.owl]
class: CommandLineTool
baseCommand: [sh, -c, 'printf x > out.wkb']
inputs: []
outputs:
  geom: {type: File, format: eo:WKB, outputBinding: {glob: out.wkb}}
